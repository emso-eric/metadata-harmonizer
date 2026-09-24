#!/usr/bin/env python3
"""
Resource management for the EMSO Metadata Harmonizer.

Resources come from two independent sources, because they have two different owners:

  manifest.json      Normative Markdown authored by EMSO ERIC. Versioned with the specifications repository
                     tags, so the user can pin an exact version. Cached under .emso/specs/<version>/.

  vocabularies.json  Vocabularies governed by third parties (NVS/SeaDataNet, Copernicus). Refreshed on their
                     own cadence, independently of the specifications version, so there is a single current
                     snapshot shared by every version, published already parsed (CSV/JSON) so that no RDF
                     toolchain is needed here. Cached under .emso/<sdn|edmo|copernicus|keywords|oso|ror>/.

SPDX and DwC are listed in neither manifest and are downloaded from their upstream projects; they are
version-independent and live at the root of the cache directory.

Downloads run in a thread pool. The work is network-bound, and the parsing that follows is cheap (~0.3 s for
the whole cache) and releases the GIL inside pandas, so processes would only add interpreter startup and
the cost of pickling large DataFrames back to the parent.

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
"""

import os
import json
import time
import logging
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

from .utils import download_file, get_file_md5

log = logging.getLogger("emso_metadata_harmonizer")

DEFAULT_CACHE_DIR = ".emso"

owner_repo = "emso-eric/emso-metadata-specifications"
raw_github = f"https://raw.githubusercontent.com/{owner_repo}"

# manifest.json is published on main at release time. While a release is still in preparation it only exists on
# develop, so both are tried in order.
manifest_urls = [
    f"{raw_github}/refs/heads/main/external-resources/manifest.json",
    f"{raw_github}/refs/heads/develop/external-resources/manifest.json",
]

# The vocabulary snapshot always tracks develop, whatever specifications version was requested.
vocabularies_urls = [f"{raw_github}/refs/heads/develop/external-resources/vocabularies.json"]

# How long a cached manifest is trusted before re-checking upstream
manifest_max_age = 24 * 3600

# Resources listed in neither manifest. Keys are (name, filename relative to the cache dir, url).
#
# OSO and the keyword vocabularies (GCMD, GEMET, EuroSciVoc) used to be downloaded here or by vocabularies.py
# and parsed from RDF at runtime. They are now published pre-parsed in vocabularies.json, so nothing below needs
# an RDF toolchain. Only SPDX and DwC remain: both are small, stable and maintained upstream on GitHub.
static_resources = [
    ("spdx_licenses", "spdx_licenses.md",
     "https://raw.githubusercontent.com/spdx/license-list-data/main/licenses.md"),
    ("dwc_terms", "dwc_terms.csv",
     "https://raw.githubusercontent.com/tdwg/dwc/refs/heads/master/vocabulary/term_versions.csv"),
]


def process_markdown_file(file) -> dict:
    """
    Processes the Markdown file and parses their tables. Every table is returned as a pandas dataframe.
    :returns: a dict wher keys are table titles and values are dataframes with the info
    """
    with open(file, encoding="utf-8") as f:
        lines = f.readlines()

    title = ""
    tables = {}
    in_table = False
    lines += "\n"  # add an empty line to force table end
    linenum = 0
    for line in lines:
        line = line.strip()
        linenum += 1
        if line.startswith("#"):  # store the title
            title = line.strip().replace("#", "").strip()

        elif not in_table and line.startswith("|"):  # header of the table
            if not line.endswith("|"):
                line += "|"  # fix tables not properly formatted
            table = {}
            headers = line.strip().split("|")
            headers = [h.strip() for h in headers][1:-1]
            headers += ["annotations"]

            for header in headers:
                table[header] = []
            in_table = True

        elif in_table and not line.startswith("|"):  # end of the table
            in_table = False
            tables[title] = pd.DataFrame(table)  # store the metadata as a DataFrame

        elif line.startswith("|---"):  # skip the title and body separator (|----|---|---|)
            continue

        elif line.startswith("|"):  # process the row
            if not line.endswith("|"):
                line += "|"  # fix tables not properly formatted
            fields = [f.strip() for f in line.split("|")[1:-1]]

            # If there's an annotation store its value  "contributors<sup>1</sup>" -> ("contributors", 1)
            if "<sup>" in fields[0]:
                a = fields[0].replace("</sup>", "")
                field, annotation = a.split("<sup>")
                annotation = int(annotation)
                fields[0] = field
            else:
                annotation = 0

            fields = [f.split("<")[0] for f in fields]  # remove annotations like <sup>1</sup>
            for i in range(len(fields)):
                if fields[i] in ["false", "False"]:
                    table[headers[i]].append(False)
                elif fields[i] in ["true", "True"]:
                    table[headers[i]].append(True)
                else:
                    table[headers[i]].append(fields[i])
            table[headers[i + 1]].append(annotation)
    return tables


def load_json(file):
    with open(file) as f:
        return json.load(f)


class Resource:
    """
    A single downloadable file: where it lives remotely, where it is cached locally, and how it is parsed.

    Parsing is driven by the file extension:
        .csv  -> self.df      a pandas DataFrame
        .md   -> self.tables  dict of table title -> DataFrame
        .json -> self.dict    the decoded document
    Any other extension (.ttl, .rdf) is left on disk untouched and get() returns its path.
    """

    def __init__(self, filename, url, md5=None, name="", key=""):
        self.filename = filename
        self.url = url
        self.md5 = md5  # None means the upstream ref is mutable and no hash can be trusted
        self.name = name  # logical resource name, e.g. "P01"
        self.key = key  # file within the resource, e.g. "csv", "narrower", "md"

        self.df = None  # CSV will be load into dataframes
        self.tables = {}  # markdown will be loaded as a dict with key=table_name value=dataframe
        self.dict = {}  # json files will be loaded directly into a dict

        self.downloaded = False
        self.error = None

    def __repr__(self):
        return f"<Resource {self.label} -> {self.filename}>"

    @property
    def label(self):
        return f"{self.name}.{self.key}" if self.key else self.name

    def is_cached(self, known_md5=None):
        """
        True if the local copy can be reused. When the manifest provides an md5 the file is only trusted if it
        matches; known_md5 is the hash recorded when the file was last downloaded, which lets the common case
        skip re-hashing the whole cache (~115 MB) on every run.
        """
        if not os.path.isfile(self.filename):
            return False
        if self.md5 is None:
            return True  # mutable ref, staleness is handled by the manifest's own max age
        if known_md5 == self.md5:
            return True  # already verified after the last download
        return get_file_md5(self.filename) == self.md5

    def download(self, force=False, known_md5=None):
        """
        Fetch the file unless a good copy is already cached. Returns the md5 of the local file, or None if it
        could not be established.
        """
        if not force and self.is_cached(known_md5=known_md5):
            log.debug(f"    {self.label} is up to date")
            return self.md5 if self.md5 else known_md5

        log.info(f"    downloading {self.label} to {self.filename}...")
        os.makedirs(os.path.dirname(self.filename) or ".", exist_ok=True)
        download_file(self.url, self.filename)
        self.downloaded = True

        local_md5 = get_file_md5(self.filename)
        if self.md5 and local_md5 != self.md5:
            # The vocabulary snapshot tracks a mutable branch: a mismatch means it moved between publishing the
            # manifest and this download, not that the file is corrupt.
            log.warning(f"{self.label}: md5 mismatch (expected {self.md5}, got {local_md5}). "
                        f"The upstream snapshot probably moved; the downloaded file is used anyway.")
        return local_md5

    def parse(self):
        """
        Parse the downloaded file depending on the extension
        """
        extension = os.path.splitext(self.filename)[1].lower()
        if extension == ".csv":
            self.df = pd.read_csv(self.filename)
        elif extension == ".md":
            self.tables = process_markdown_file(self.filename)
        elif extension == ".json":
            self.dict = load_json(self.filename)
        else:
            log.debug(f"    {self.label}: extension '{extension}' not parsed, keeping file as-is")

    def process(self, force=False, known_md5=None):
        """
        Download and parse. Exceptions are captured so that one failing resource does not take down the whole
        thread pool; ResourceManager re-raises them after every task has finished.
        """
        try:
            local_md5 = self.download(force=force, known_md5=known_md5)
            self.parse()
            return local_md5
        except Exception as e:
            self.error = e
            log.error(f"Could not process {self.label}: {e}")
            return None

    def get(self):
        """
        Return the parsed contents: a DataFrame for CSV, a dict of tables for Markdown, a dict for JSON, or the
        local path for anything that is not parsed.
        """
        if self.df is not None:
            return self.df
        if self.tables:
            return self.tables
        if self.dict:
            return self.dict
        return self.filename


class ResourceManager:
    """
    Resolves the requested specifications version, downloads everything it needs in parallel and exposes the
    parsed results.

        rm = ResourceManager(version="v1.0.7")
        rm.get("P01", "csv")                    # DataFrame
        rm.get("EMSO_Metadata_Specifications")  # dict of tables
        rm.path("OSO")                          # local path of the ontology
    """

    def __init__(self, version="", cache_dir=DEFAULT_CACHE_DIR, force_update=False, max_threads=10,
                 specs_file=""):
        """
        :param version: specifications version ("v1.0.7", "develop", "latest" or empty for the default)
        :param cache_dir: directory holding the downloaded resources
        :param force_update: re-download everything, ignoring the cache
        :param max_threads: size of the download thread pool
        :param specs_file: local EMSO_Metadata_Specifications.md overriding the published one (development)
        """
        self.cache_dir = cache_dir
        self.force_update = force_update
        self.max_threads = max_threads
        self.specs_file = specs_file

        os.makedirs(self.cache_dir, exist_ok=True)

        self.__state_file = os.path.join(self.cache_dir, ".cache_state.json")
        self.__state = load_json(self.__state_file) if os.path.isfile(self.__state_file) else {}

        self.manifest = self.get_manifest()  # Manifest contains version-tagged EMSO-specification documents
        self.vocabularies = self.get_vocabularies()

        self.version = self.resolve_version(version)
        log.info(f"Using EMSO Metadata Specifications {self.version}")

        self.resources = {}  # name -> {key: Resource}
        self.__build_resources()
        self.download_resources()

    # ------------------------------------------------------------------ manifests
    def __cached_manifest_file(self, name):
        return os.path.join(self.cache_dir, name)

    def __fetch_manifest(self, urls, filename, what):
        """
        Download a manifest, falling back to the cached copy when it cannot be reached. The cached copy is
        reused without any network access while it is younger than manifest_max_age.
        """
        cached = load_json(filename) if os.path.isfile(filename) else None

        if cached and not self.force_update:
            age = time.time() - os.path.getmtime(filename)
            if age < manifest_max_age:
                log.debug(f"{what} is recent enough ({age / 3600:.1f} h), not checking upstream")
                return cached

        for url in urls:
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                document = response.json()
            except (requests.exceptions.RequestException, ValueError) as e:
                log.debug(f"Could not fetch {what} from {url}: {e}")
                continue

            os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
            tmp = filename + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(document, f, indent=2)
            os.replace(tmp, filename)  # single atomic write
            log.debug(f"{what} updated from {url}")
            return document

        if cached:
            log.warning(f"Could not reach any {what} URL, using the cached copy")
            os.utime(filename, None)  # back off instead of retrying on every call
            return cached

        raise RuntimeError(f"Could not download {what} from {urls} and no cached copy exists in "
                           f"'{self.cache_dir}'. Check the network connection.")

    def get_manifest(self):
        """
        Gets the manifest listing every published specifications version and its normative documents.
        """
        return self.__fetch_manifest(manifest_urls, self.__cached_manifest_file("manifest.json"), "manifest.json")

    def get_vocabularies(self):
        """
        Gets the current snapshot of the externally governed vocabularies. Not version-dependent.
        """
        return self.__fetch_manifest(vocabularies_urls, self.__cached_manifest_file("vocabularies.json"),
                                     "vocabularies.json")

    def available_versions(self):
        return list(self.manifest.get("versions", {}).keys())

    def resolve_version(self, version: str) -> str:
        """
        Turn a user-supplied version into a key of the manifest. An empty value or "latest" resolves to the
        manifest default.
        """
        versions = self.manifest.get("versions", {})
        if not version or version == "latest":
            resolved = self.manifest.get("default") or self.manifest.get("latest")
            if resolved not in versions:
                raise ValueError(f"Manifest default '{resolved}' is not a listed version")
            return resolved

        if version in versions:
            return version

        raise ValueError(f"EMSO Metadata Specifications version '{version}' not found. "
                         f"Available versions: {', '.join(versions.keys())}")

    # ------------------------------------------------------------------ resources
    def __add(self, name, key, filename, url, md5=None):
        self.resources.setdefault(name, {})[key] = Resource(filename, url, md5=md5, name=name, key=key)

    def __build_resources(self):
        """
        Create one Resource per file: the normative documents of the selected version, the current vocabulary
        snapshot, and the static third-party resources.
        """
        # ---- normative documents, cached per version so that switching version cannot mix them up
        entry = self.manifest["versions"][self.version]
        specs_dir = os.path.join(self.cache_dir, "specs", self.version)
        for name, meta in entry["files"].items():
            filename = os.path.join(specs_dir, *meta["path"].split("/"))
            self.__add(name, "md", filename, entry["base_url"] + meta["path"], md5=meta.get("md5"))

        # ---- vocabularies, shared by every version. The local layout mirrors the repository layout minus the
        # external-resources/ prefix, which is also where vocabularies.py expects to find them.
        for name, resource in self.vocabularies["resources"].items():
            for key, meta in resource["files"].items():
                relative = meta["path"].replace("external-resources/", "", 1)
                filename = os.path.join(self.cache_dir, *relative.split("/"))
                self.__add(name, key, filename, self.vocabularies["base_url"] + meta["path"],
                           md5=meta.get("md5"))

        # ---- static resources, owned by neither manifest
        for name, relative, url in static_resources:
            self.__add(name, "file", os.path.join(self.cache_dir, relative), url)

    def __all_resources(self):
        return [r for files in self.resources.values() for r in files.values()]

    def download_resources(self):
        """
        Download and parse every resource in parallel. Downloads dominate the cost and release the GIL, so a
        thread pool is the right tool here.
        """
        resources = self.__all_resources()
        log.info(f"Loading {len(resources)} EMSO metadata resources ({self.max_threads} threads)...")
        t = time.time()

        def worker(resource):
            return resource, resource.process(force=self.force_update,
                                              known_md5=self.__state.get(resource.filename))

        with ThreadPoolExecutor(max_workers=self.max_threads) as pool:
            results = list(pool.map(worker, resources))

        failed = [r for r in resources if r.error]
        if failed:
            raise RuntimeError(
                f"Could not load {len(failed)} of {len(resources)} resources: "
                f"{', '.join(r.label for r in failed)}. First error: {failed[0].error}") from failed[0].error

        # Remember the verified hashes so the next run does not have to re-read the whole cache
        for resource, local_md5 in results:
            if local_md5:
                self.__state[resource.filename] = local_md5
        self.__save_state()

        downloaded = sum(1 for r in resources if r.downloaded)
        log.info(f"Loaded {len(resources)} resources in {time.time() - t:.02f} s "
                 f"({downloaded} downloaded, {len(resources) - downloaded} from cache)")

    def __save_state(self):
        try:
            tmp = self.__state_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.__state, f, indent=2)
            os.replace(tmp, self.__state_file)
        except OSError as e:
            log.debug(f"Could not write the cache state file: {e}")  # purely an optimisation, never fatal

    # ------------------------------------------------------------------ accessors
    def __contains__(self, name):
        return name in self.resources

    def resource(self, name, key=None) -> Resource:
        if name not in self.resources:
            raise KeyError(f"Resource '{name}' not available. Known resources: "
                           f"{', '.join(sorted(self.resources.keys()))}")
        files = self.resources[name]
        if key is None:
            if len(files) != 1:
                raise KeyError(f"Resource '{name}' holds several files {sorted(files.keys())}, pick one")
            key = next(iter(files))
        if key not in files:
            raise KeyError(f"Resource '{name}' has no file '{key}', available: {sorted(files.keys())}")
        return files[key]

    def get(self, name, key=None):
        """
        Parsed contents of a resource: DataFrame, dict of tables, dict, or a path when it is not parsed.
        """
        return self.resource(name, key).get()

    def path(self, name, key=None) -> str:
        """
        Local path of a resource, for consumers that need the file rather than its contents.
        """
        return self.resource(name, key).filename

    def as_local_resources(self) -> dict:
        """
        The resource layout used before manifest.json existed: {name: {key: local path}}. Kept so that code
        reading EmsoMetadata.local_resources keeps working.
        """
        return {name: {key: r.filename for key, r in files.items()} for name, files in self.resources.items()}
