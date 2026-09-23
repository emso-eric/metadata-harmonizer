#!/usr/bin/env python3
"""
This script contains tools to access, download and parse Metadata stored in Markdown format within EMSO ERIC's github
repository.

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 3/3/23
"""
import logging
import os
from .vocabularies import GEMET, GCMD, SeaDataNetVocabulary, EuroSciVoc, Keyword, OSO
from .utils import get_file_list, assert_type
from .resource_manager import ResourceManager, process_markdown_file, load_json

# Specifications version used when the caller does not ask for one. "develop" keeps the behaviour of previous
# releases; set it to "latest" to follow the newest published tag instead.
emso_version = "develop"

log = logging.getLogger("emso_metadata_harmonizer")

user_defined_specs_file = ""  # used to overload online specifications, used for development only

# Downloading, caching and parsing now lives in resource_manager.py. process_markdown_file and load_json are
# re-exported here because they used to be defined in this module.
__all__ = ["EmsoMetadata", "KeywordValidator", "init_emso_metadata", "process_markdown_file", "load_json"]


emso_metadata_object = None
def init_emso_metadata(force_update=False):
    """
    Wrapper to avoid called EmsoMetadata twice
    """
    global emso_metadata_object
    if not emso_metadata_object:
        emso_metadata_object = EmsoMetadata(force_update=force_update)

    return emso_metadata_object


class KeywordValidator:
    def __init__(self, vocabularies: list):
        self.vocabularies = vocabularies

        self.valid_vocabs = [v.name for v in self.vocabularies]
        self.valid_vocabs_uri = [v.uri for v in self.vocabularies]

    def keyword_from_label(self, term: str) -> Keyword:
        assert isinstance(term, str), f"Expected string, got {type(term)}"
        for vocab in self.vocabularies:
            # If found in a vocabulary return the Keyword object
            k = vocab.validate_label(term)
            if k:  # check if the created Keyword is valid
                return k

        return Keyword(term, "", None)

    def keyword_from_uri(self, uri: str) -> Keyword | None:
        assert isinstance(uri, str), f"Expected string, got {type(uri)}"
        for vocab in self.vocabularies:
            k = vocab.validate_uri(uri)
            if k:
                return k
        return Keyword("", uri, None)


    def used_vocabularies(self, keywords: list):
        """
        From a list of keywords, return a list of the used vocabularies names and URIs
        """
        titles = []
        uris = []
        for keyword in keywords:
            if not keyword:
                continue

            assert isinstance(keyword, Keyword), f"Expected Keyword, got {type(keyword)}"

            if keyword.vocab_name not in titles:
                titles.append(keyword.vocab_name)
            if keyword.vocab_uri not in uris:
                uris.append(keyword.vocab_uri)

        assert len(titles) == len(uris)
        return titles, uris


class EmsoMetadata:
    def __init__(self, force_update=False, version="", max_threads=10):
        """
        :param force_update: re-download every resource, ignoring the cache
        :param version: EMSO Metadata Specifications version. Empty uses the module default (see emso_version)
        :param max_threads: size of the download thread pool
        """
        log.info("Loading EMSO Metadata resources...")

        # All downloading, caching and parsing is delegated to the ResourceManager, which resolves the
        # requested version against manifest.json and fetches everything in parallel.
        self.resource_manager = ResourceManager(version=version or emso_version, force_update=force_update,
                                                max_threads=max_threads, specs_file=user_defined_specs_file)
        self.specs_version = self.resource_manager.version
        # Kept for backwards compatibility: {resource name: {file key: local path}}
        self.local_resources = self.resource_manager.as_local_resources()

        # TODO: Move hardcoded levels to proper markdown file. Data_Processing_Levels.md is now published in
        #       manifest.json (v1.0.4 onwards), so this can read self.resource_manager.get("Data_Processing_Levels")
        self.data_processing_levels = ["L0", "L1", "L2"]
        self.data_processing_steps = ["L0a", "L0b", "L1a", "L1b", "L1c", "L1d"]

        # TODO: Now SeaDataNet / BODC vocabularies are parsed twice, one here and a second time as GenericVocabulary. It should be unified
        self.sdn_vocabs = {
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
        self.sdn_vocabs_narrower = {}
        self.sdn_vocabs_broader = {}
        self.sdn_vocabs_related = {}
        self.sdn_vocabs_pref_label = {}
        self.sdn_vocabs_alt_label = {}
        self.sdn_vocabs_ids = {}
        self.sdn_vocabs_uris = {}

        # ==== Load all SDN vocabularies ==== #
        # Every file was already downloaded and parsed by the ResourceManager, so this is just a re-shuffle
        for vocab in list(self.sdn_vocabs.keys()):
            log.debug(f"    loading SDN vocabulary {vocab}")
            df = self.resource_manager.get(vocab, "csv")
            self.sdn_vocabs[vocab] = df
            self.sdn_vocabs_narrower[vocab] = self.resource_manager.get(vocab, "narrower")
            self.sdn_vocabs_broader[vocab] = self.resource_manager.get(vocab, "broader")
            self.sdn_vocabs_related[vocab] = self.resource_manager.get(vocab, "related")
            self.sdn_vocabs_pref_label[vocab] = df["prefLabel"].values
            self.sdn_vocabs_alt_label[vocab] = df["altLabel"].values
            self.sdn_vocabs_ids[vocab] = df["id"].values
            self.sdn_vocabs_uris[vocab] = df["uri"].values

        # ==== Load Copernicus Variables ==== #
        log.debug(f"    loading Copernicus Parameters")
        tables = self.resource_manager.get("Copernicus Parameters", "md")

        self.copernicus_variables = tables["Copernicus variables"]["variable name"].to_list()
        log.debug(f"    loading EDMO codes")
        self.edmo_codes = self.resource_manager.get("EDMO", "csv")

        if user_defined_specs_file:
            log.warning(f"Using custom specifications file: {user_defined_specs_file}")
            tables = process_markdown_file(user_defined_specs_file)
        else:
            tables = self.resource_manager.get("EMSO_Metadata_Specifications", "md")

        self.global_attr = tables["Global Attributes"]
        self.env_coordinate_attr = tables["Coordinate Variables"]

        self.cor_variables_attr = tables["Coordinate Variables"]
        self.env_variables_attr = tables["Environmental Variables"]
        self.bio_variables_attr = tables["Biological Variables"]
        self.qc_variables_attr = tables["Quality Control Variables"]
        self.tec_variables_attr = tables["Technical Variables"]
        self.sensor_variables_attr = tables["Sensor Variables"]
        self.platform_variables_attr = tables["Platform Variables"]
        self.valid_coordinates = tables["Valid Coordinates"]

        tables = self.resource_manager.get("OceanSites_codes", "md")
        self.oceansites_sensor_mount = tables["Sensor Mount"]["sensor_mount"].to_list()
        self.oceansites_sensor_orientation = tables["Sensor Orientation"]["sensor_orientation"].to_list()
        self.oceansites_data_modes = tables["Data Modes"]["Value"].to_list()
        self.oceansites_data_types = tables["Data Types"]["Data type"].to_list()
        self.oceansites_param_codes = tables["Variable Names"]["Parameter"].to_list()

        tables = self.resource_manager.get("DataCite_codes", "md")
        self.datacite_contributor_roles = tables["DataCite Contributor Type"]["Type"].to_list()

        tables = self.resource_manager.get("spdx_licenses", "file")
        t = tables["Licenses with Short Identifiers"]

        # remove extra '[' ']' in license identifiers
        new_ids = [value.replace("[", "").replace("]", "") for value in t["Short Identifier"]]
        self.spdx_license_names = new_ids
        self.spdx_license_uris = {lic: f"https://spdx.org/licenses/{lic}" for lic in self.spdx_license_names}

        df = self.resource_manager.get("dwc_terms", "file")
        df = df[["term_localName", "term_iri"]]
        df = df.rename(columns={"term_localName": "name", "term_iri": "uri"})
        self.dwc_terms = df

        # Convert P02 IDs to 4-letter codes
        self.sdn_p02_names = [code.split(":")[-1] for code in self.sdn_vocabs_ids["P02"]]

        # Every vocabulary below is built from tables the ResourceManager already downloaded and parsed. The
        # RDF graphs they used to be derived from are now processed upstream, in the specifications repository.
        rm = self.resource_manager
        self.oso = OSO(rm.get("OSO", "csv"), rm.get("OSO", "platforms"), rm.get("OSO", "sites"),
                       rm.get("OSO", "rfs"), rm.get("OSO", "platform_metadata"))
        gcmd = GCMD(rm.get("GCMD", "csv"))
        euroscivoc = EuroSciVoc(rm.get("EuroSciVoc", "csv"))
        gemet = GEMET(rm.get("GEMET", "csv"))
        P02 = SeaDataNetVocabulary("P02", rm.get("P02", "csv"))
        L05 = SeaDataNetVocabulary("L05", rm.get("L05", "csv"))
        L06 = SeaDataNetVocabulary("L06", rm.get("L06", "csv"))
        L22 = SeaDataNetVocabulary("L22", rm.get("L22", "csv"))
        P07 = SeaDataNetVocabulary("P07", rm.get("P07", "csv"))
        self.keywords = KeywordValidator([gemet, euroscivoc, gcmd, P02, L05, L06, L22, P07, self.oso])

    @staticmethod
    def version():
        """
        Specifications version that will be used by the next EmsoMetadata. Once built, the resolved version is
        available as EmsoMetadata().specs_version ("latest" is resolved against the manifest).
        """
        return emso_version

    @staticmethod
    def set_version(version: str):
        """
        Select the EMSO Metadata Specifications version. Accepts a version listed in manifest.json
        ("v1.0.7", "develop"), the alias "latest", or the path to a local EMSO_Metadata_Specifications.md
        used to override the published one during development.
        """
        assert_type(version, str)
        global emso_version, user_defined_specs_file
        if version.endswith(".md"):
            assert os.path.isfile(version), f"File {version} does not exist"
            user_defined_specs_file = version
        elif version:
            # "latest" is resolved by the ResourceManager against the manifest's default version
            emso_version = version

    @staticmethod
    def use_custom_file(filename):
        """
        Override the published specifications with a local Markdown file (development only).
        """
        global user_defined_specs_file
        user_defined_specs_file = filename

    @staticmethod
    def available_versions():
        """
        Versions listed in the published manifest, most recent last.
        """
        return ResourceManager(version=emso_version).available_versions()

    @staticmethod
    def clear_downloads():
        """
        Clears all files in .emso folder
        """
        files = get_file_list(".emso")
        for f in files:
            if os.path.isfile(f):
                os.remove(f)

    @staticmethod
    def harmonize_sdn_uri(uri):
        """
        Takes a SDN URI and make sure that uses http instead of https and that it finishes with a /
        """
        if uri.startswith("https"):
            uri = uri.replace("https", "http")

        if not uri.endswith("/"):
            uri += "/"
        return uri

    def vocab_get(self, vocab_id, uri, key):
        """
        Search in vocab <vocab_id> for the element with matching uri and return element identified by key
        """
        log = logging.getLogger()

        uri = self.harmonize_sdn_uri(uri)
        __allowed_keys = ["prefLabel", "id", "definition", "altLabel"]
        if key not in __allowed_keys:
            raise ValueError(f"Key '{key}' not valid, allowed keys: {__allowed_keys}")

        df = self.sdn_vocabs[vocab_id]
        row = df.loc[df["uri"] == uri]
        if row.empty:
            #raise LookupError(f"Could not get {key} for '{uri}' in vocab {vocab_id}")
            log.warning(f"Could not get {key} for '{uri}' in vocab {vocab_id}")
            return

        return row[key].values[0]

    def get_vocab_by_uri(self, vocab_id, uri) -> (str, str, str, str):
        """
        Search in vocab <vocab_id> for the element with matching uri and return element identified by key
        :param vocab_id:
        :param uri: uri
        :returns: tuple of (uri, urn, prefLabel, altlabel)
        """
        uri = self.harmonize_sdn_uri(uri)
        df = self.sdn_vocabs[vocab_id]
        row = df.loc[df["uri"] == uri]
        if row.empty:
            raise LookupError(f"Could not find '{uri}' in vocab {vocab_id}")
        return row["uri"].values[0], row["id"].values[0], row["prefLabel"].values[0], row["altLabel"].values[0]


    def get_vocab_by_urn(self, vocab_id, urn):
        """
        Search in vocab <vocab_id> for the element with matching uri and return element identified by key
        """
        uri = self.harmonize_sdn_uri(urn)
        df = self.sdn_vocabs[vocab_id]
        row = df.loc[df["uri"] == uri]
        if row.empty:
            raise LookupError(f"Could not find '{uri}' in vocab {vocab_id}")
        return row["uri"].values[0], row["id"].values[0], row["prefLabel"].values[0], row["altLabel"].values[0]

    def get_relations(self, vocab_id, uri, relation, target_vocab):
        """
        Takes a relation list from a vocabulary (narrower, broader or related), looks for a term identified by URI and
        returns a list of all the terms within that relationtship that are from the vocabuary target_vocab.

        This function is useful to get related metadata from a term, from instance

            "P01", <param>, "related", "P06" -> get the prefered units for a parameter listed within P01
            "L22", <model>, "related", "L35" -> get the  manufacturer of a sensor
            "P02", <param>, "narrower", "P01" -> get all possible fine-grained parameters values from a braod parameter

        :param vocab_id: ID of the vocabulary being used
        :param uri: URI of the term whose relations will be explored
        :param relation: type of relationship, possible values are narrower, broader and related
        :param target_vocab: id of the vocabulary terms that we want to find
        :returns: list with matches
        """
        log = logging.getLogger()
        __valid_relations = ["narrower", "broader", "related"]
        uri = self.harmonize_sdn_uri(uri)

        if relation not in __valid_relations:
            raise LookupError(f"Not a valid relation: '{relation}', expected one of '{__valid_relations} ")

        if relation == "narrower":
            relations = self.sdn_vocabs_narrower[vocab_id]
        elif relation == "broader":
            relations = self.sdn_vocabs_broader[vocab_id]
        else:  # related
            relations = self.sdn_vocabs_related[vocab_id]

        try:
            uri_relations = relations[uri]
        except KeyError:
            log.warning(f"relation {relation} for {uri} not found!")
            return ""

        if type(uri_relations) is str:  # make sure it's a list
            uri_relations = [uri_relations]

        results = []
        for term in uri_relations:
            if target_vocab in term:
                results.append(term)
        return results

    def get_relation(self, vocab_id, uri, relation, target_vocab):
        """
        The same as get relations but throws an error if more than one element are found
        """
        log = logging.getLogger()
        results = self.get_relations(vocab_id, uri, relation, target_vocab)
        if len(results) == 0:
            log.warning(f"Could not find relation {relation} for {uri}")
            return ""
        elif len(results) != 1:
            raise LookupError(f"Expected 1 value, got {len(results)}")

        return results[0]

    def list_to_str(self, attr: str, value: list):

        """
        Converts list to string. Check if the attribute is expected to use comma as a separator or will use just a blank space.
        """
        assert_type(attr, str)
        assert_type(value, list)
        if not value:
            return ""
        df = self.global_attr
        separator = " "
        if attr in df["Global Attributes"].to_list():
            # Get the annotation value in the table, if it is 1 means comma separator, otherwise space
            annotation = df[df["Global Attributes"] == attr]["annotations"].values[0]
            if annotation == 1: # annotation "1" means comma-separated
                separator = ", "

        return separator.join(value)

