import logging
import pandas as pd
from typing import Optional, Dict
import os
from rdflib import Graph, Namespace, RDF
import time
import gzip
from src.emso_metadata_harmonizer.metadata.utils import threadify
from collections import defaultdict
import requests


def rdf_to_dataframe(file: str) -> pd.DataFrame:
    log = logging.getLogger()
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
    g = Graph()
    log.debug(f"Parsing file {file}...")
    t = time.time()
    g.parse(file, format="xml")
    log.debug(f"File parsed in {time.time() - t:.2f}s")

    # 1. Single-pass: collect all prefLabels for SKOS Concepts
    uri_to_label = {}
    for s, _, label in g.triples((None, SKOS.prefLabel, None)):
        # Skip if we already have an English label
        if s in uri_to_label and getattr(uri_to_label[s], 'language', None) == 'en':
            continue
        if not hasattr(label, 'language') or label.language in (None, 'en'):
            uri_to_label[s] = str(label)

    # 2. Single-pass: collect all broader relationships
    child_to_parent = {s: o for s, o in g.subject_objects(SKOS.broader)}

    # 3. Build paths iteratively (no recursion overhead)
    def get_path(uri):
        path = []
        current = uri
        seen = set()  # guard against cycles
        while current in child_to_parent:
            if current in seen:
                break
            seen.add(current)
            label = uri_to_label.get(current)
            if label:
                path.append(label)
            current = child_to_parent[current]
        top_label = uri_to_label.get(current)
        if top_label:
            path.append(top_label)
        return path[::-1]

    # 4. Build all paths
    all_paths = [path for uri in uri_to_label if (path := get_path(uri))]

    # 5. Build DataFrame
    df = pd.DataFrame(all_paths)
    df.columns = [f"level{i}" for i in range(df.shape[1])]
    return df.sort_values(by=list(df.columns)).drop_duplicates().reset_index(drop=True)

class KeywordList:
    def __init__(self) -> None:
        self.terms = []
        self.terms_lc = []

    def validate_term(self, term: str):
        """
        Return values: perfect_match, partial_match
        """
        assert isinstance(term, str), f"Expected string, got {type(term)} instead"
        assert len(self.terms) > 0, f"List of terms is empty!"

        if len(self.terms_lc) == 0:
            self.terms_lc = [t.lower() for t in self.terms if isinstance(t, str)]

        term = term
        term_lc = term.lower()

        if term in self.terms:
            return True, False

        if term_lc in self.terms_lc:
            return False, True

        else:
            return False, False

    def set_terms(self, df_list: list, cols=[]):
        for df in df_list:
            if not cols:
                # By default, process ALL columns in the dataframe
                columns = df.columns
            else:
                # use column subset
                columns = cols

            for c in columns:
                self.terms += df[c].unique().tolist()


class EuroSciVoc(KeywordList):
    def __init__(self):
        super().__init__()
        self.name = "EuroSciVoc"
        download_uri  = "https://op.europa.eu/o/opportal-service/euvoc-download-handler?cellarURI=http%3A%2F%2Fpublications.europa.eu%2Fresource%2Fdistribution%2Feuroscivoc%2F20250924-0%2Frdf%2Fskos_xl%2FEuroSciVoc.rdf&fileName=EuroSciVoc.rdf"
        self.uri = "https://op.europa.eu/en/web/eu-vocabularies/euroscivoc"
        rdf_file = os.path.join(".emso", "keywords", "euroscivoc", "euroscivoc.rdf")
        csv_file = os.path.join(".emso", "keywords", "euroscivoc", "euroscivoc.csv")
        df = self.__load(download_uri, csv_file, rdf_file)
        self.__terms = []  # list of all EuroSciVoc terms
        self.set_terms([df])


    @staticmethod
    def __load(uri, csv_file, rdf_file) -> pd.DataFrame:
        log = logging.getLogger()
        if os.path.exists(csv_file):
            log.debug(f"Loading EuroSciVoc from local file '{csv_file}'")
            # Load the parsed file (faster option)
            df = pd.read_csv(csv_file)
            return df

        elif not os.path.exists(rdf_file):
            # If RDF file does not exist
            log.debug(f"Downloading EuroSciVoc to {rdf_file}")
            download_file(uri, rdf_file)

        log.debug(f"Loading EuroSciVoc from RDF file {rdf_file}")
        format_type = "xml"  # rdf is xml
        g = Graph()
        g.parse(rdf_file, format=format_type)

        # Namespaces
        SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
        SKOSXL = Namespace("http://www.w3.org/2008/05/skos-xl#")

        # -------------------------
        # Build hierarchy
        # -------------------------
        children = defaultdict(list)
        parents = defaultdict(list)

        for s, o in g.subject_objects(SKOS.broader):
            children[o].append(s)
            parents[s].append(o)

        # -------------------------
        # Label function (EN only)
        # -------------------------
        def get_label_en(concept):
            for label_node in g.objects(concept, SKOSXL.prefLabel):
                for literal in g.objects(label_node, SKOSXL.literalForm):
                    if literal.language == "en":
                        return str(literal)
            return None  # skip if no English label

        # -------------------------
        # Find roots
        # -------------------------
        concepts = set(g.subjects(RDF.type, SKOS.Concept))
        roots = [c for c in concepts if c not in parents]

        # -------------------------
        # Traverse and collect paths
        # -------------------------
        paths = []

        def traverse(concept, path):
            label = get_label_en(concept)
            if label is None:
                return  # skip non-English nodes

            new_path = path + [label]
            paths.append(new_path)

            for child in children.get(concept, []):
                traverse(child, new_path)

        # Run traversal
        for root in roots:
            traverse(root, [])

        # -------------------------
        # Determine max depth
        # -------------------------
        max_depth = max(len(p) for p in paths)

        # -------------------------
        # Normalize to wide format
        # -------------------------
        rows = []
        for p in paths:
            row = p + [""] * (max_depth - len(p))  # pad with empty strings
            rows.append(row)

        columns = [f"level_{i}" for i in range(max_depth)]

        df = pd.DataFrame(rows, columns=columns)

        # Optional: remove duplicates
        df = df.drop_duplicates()
        log.debug(f"Storing parsed EuroSciVoc to CSV file {csv_file}")
        df.to_csv(csv_file, index=False)
        return df


def download_file(url: str, filename: str, headers: Optional[Dict[str, str]] = None, chunk_size: int = 8192) -> None:
    """
    Download a file from a URL and save it to disk.

    Args:
        url: The URL to download from
        filename: The local path where to save the file
        headers: Optional HTTP headers to include in the request
        chunk_size: Size of chunks to stream the download (default 8KB)
    """
    if headers is None:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; DataDownloader/1.0)',
            'Accept': '*/*'
        }

    response = requests.get(url, headers=headers, stream=True)
    response.raise_for_status()

    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)

    with open(filename, 'wb') as file:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                file.write(chunk)

class GCMD(KeywordList):
    def __init__(self) -> None:
        super().__init__()
        self.name = "GCMD Science Keywords"
        uri = "https://cmr.earthdata.nasa.gov/kms/concepts/concept_scheme/sciencekeywords?format=csv"
        self.uri = "https://gcmd.earthdata.nasa.gov/"
        folder = ".emso/keywords/gcmd"
        csv_file = os.path.join(folder, "gcmd.csv")
        if not os.path.exists(csv_file):
            download_file(uri, csv_file)
        df = pd.read_csv(csv_file, skiprows=1)
        del df["UUID"]
        self.set_terms([df])

    def set_terms(self, dataframes):
        """
        GCMD uses the full path instead of the prefLabel.
        E.g. instead of "Atmospheric Pressure Measurements" the following is expected:
        "Earth Science > Atmosphere > Atmospheric Pressure > Atmospheric Pressure Measurements"
        """
        full_path = []
        self.terms = []
        for df in dataframes:
            for _, row in df.iterrows():
                non_empty = row.dropna().loc[row.dropna().astype(bool)]
                # Convert all to string (in case of numbers) and join
                row_str = " > ".join(non_empty.astype(str))
                full_path.append(row_str)
            self.terms += full_path


class GEMET(KeywordList):
    def __init__(self):
        super().__init__()
        self.name = "GEMET"
        log = logging.getLogger()
        gzip_file = os.path.join(".emso", "keywords", "gemet", "gemet.rdf.gz")
        rdf_file = os.path.join(".emso", "keywords", "gemet", "gemet.rdf")
        csv_file = os.path.join(".emso", "keywords", "gemet", "gemet.csv")

        url = "https://www.eionet.europa.eu/gemet/latest/gemet.rdf.gz"
        self.uri = "https://www.eionet.europa.eu/gemet/"

        if os.path.exists(csv_file):
            log.debug(f"Loading GEMET from CSV file {csv_file}")
            df = pd.read_csv(csv_file)
        else:
            if not os.path.exists(rdf_file):
                log.info(f"Downloading GEMET to GZ file {gzip_file}, this may take a while...")
                download_file(url, gzip_file)
                log.debug(f"Uncompressing to RDF file")
                with gzip.open(gzip_file, 'rt', encoding='utf-8') as f:
                    with open(rdf_file, "w") as fout:
                        content = f.read()
                        cleaned_content = content.replace(
                            'rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime"></dcterms:created>',
                            '></dcterms:created>')
                        cleaned_content = cleaned_content.replace(
                            'rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime"></dcterms:modified>',
                            '></dcterms:modified>')
                        fout.write(cleaned_content)

            log.debug(f"Parsing GEMET RDF file {rdf_file}, this can take a while...")
            df = rdf_to_dataframe(rdf_file)

            log.debug(f"Saving GEMET as CSV file {csv_file}")
            df.to_csv(csv_file, index=False)

        self.set_terms([df])


class SeadatanetKeyword(KeywordList):
    # SeaDataNet should already be parsed
    def __init__(self, csv_file):
        super().__init__()
        # Names are hardcoded here, since the title is in the RDF 
        names = {
            # identifier: title
            "P01": "BODC Parameter Usage Vocabulary",
            "P02": "SeaDataNet Parameter Discovery Vocabulary",
            "P06": "BODC-approved data storage units",
            "P07": "Climate and Forecast Standard Names",
            "L05": "SeaDataNet device categories",
            "L06": "SeaVoX Platform Categories",
            "L22": "SeaVoX Device Catalogue",
            "L35": "SenseOcean device developers and manufacturers"
        }
        df = pd.read_csv(csv_file)
        code = os.path.basename(csv_file).split(".")[0]
        self.name = names[code]

        self.uri = f"https://vocab.nerc.ac.uk/collection/{code}/current/"
        self.set_terms([df], cols=["prefLabel"])



