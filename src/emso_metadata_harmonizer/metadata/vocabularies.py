"""
This file contains the logic to parse and build controlled vocabularies using the GenericVocabulary class. All further
vocabularies should inherit from this class.

Vocabularies arrive already parsed. Downloading the source RDF, merging and querying the graphs and deriving the
CSV/JSON tables happens in the emso-metadata-specifications repository (external-resources/update_resources.py),
and the results are published through vocabularies.json. This module only turns those tables into lookup
structures, so the harmonizer needs no RDF toolchain and no downloads of its own.
"""
import logging
import pandas as pd
from .utils import LoggerSuperclass, BLU



class GenericVocabulary(LoggerSuperclass):
    def __init__(self, code, name, uri) -> None:

        log = logging.getLogger()
        LoggerSuperclass.__init__(self, log, code, colour=BLU)

        self.labels = []  # labels as they are
        self.labels_lc = []  # labels as lower case for easier comparison
        self.uris = []

        self.__uri_from_label = {}
        self.__label_from_uri = {}
        self.code = code
        self.name = name
        self.uri = uri

    def validate_label(self, label: str) -> "Keyword":
        """
        Return values: perfect_match, partial_match
        """
        assert isinstance(label, str), f"Expected string, got {type(label)} instead"
        assert len(self.labels) > 0, f"'{self.name}' list of terms is empty!"

        label_lc = label.lower()

        if label_lc in self.labels_lc:  # If the label is found
            uri = self.uri_from_label(label)
            return Keyword(label, uri, self)

        return Keyword(label, "", None)  # empty keyword

    def validate_uri(self, uri: str) -> "Keyword":
        return self._validate_uri(uri)

    def _validate_uri(self, uri: str) -> "Keyword":
        """
        Return values: perfect_match, partial_match
        """
        assert isinstance(uri, str), f"Expected string, got {type(uri)} instead"
        assert len(self.uris) > 0, f"'{self.name}' list of uris is empty!"

        if uri in self.uris:  # If the label is found
            label = self.label_from_uri(uri)
            return Keyword(label, uri, self)

        return Keyword("", uri, None)  # empty keyword"

    def set_terms(self, labels: list, uris: str):
        assert isinstance(labels, list), f"Expected list, got {type(labels)} instead"
        assert isinstance(uris, list), f"Expected list, got {type(uris)} instead"
        assert len(labels) == len(uris), f"Expected same number of labels and uris {len(labels)}!={len(uris)}"
        self.labels = labels
        self.uris = uris

        for label, uri in zip(labels, uris):
            # Ignore anything that is not a string
            if isinstance(label, str) and isinstance(uri, str):
                self.__uri_from_label[label.lower()] = uri

        for label, uri in zip(labels, uris):
            if isinstance(label, str) and isinstance(uri, str):
                self.__label_from_uri[uri] = label


        self.labels_lc = list(self.__uri_from_label.keys())


    def uri_from_label(self, label):
        try:
            uri = self.__uri_from_label[label.lower()]
        except KeyError as e:
            self.error(f"Label {label} not registered!")
            raise e
        return  uri

    def label_from_uri(self, uri):
        try:
            label = self.__label_from_uri[uri]
        except KeyError as e:
            self.error(f"Label {uri} not registered!")
            raise e
        return label

    def load_dataframe(self, df: pd.DataFrame):
        """
        Load a pre-parsed vocabulary table. The table is produced by update_resources.py in the
        emso-metadata-specifications repository and must expose a 'uri' and a 'prefLabel' column.
        """
        assert isinstance(df, pd.DataFrame), f"Expected DataFrame, got {type(df)}"
        assert len(df) > 0, f"Vocabulary '{self.name}' is empty!"
        for column in ["uri", "prefLabel"]:
            assert column in df.columns, f"Column '{column}' not found in vocabulary '{self.name}'!"
        self.set_terms(df["prefLabel"].to_list(), df["uri"].to_list())
        self.debug(f"Loaded {len(df)} terms")

    def __repr__(self):
        s = "----------------------------------------\n"
        s += f"Vocabulary: '{self.name}'\n"
        s += f"       uri: {self.uri}\n"
        s += f"     terms: {len(self.terms)}\n"
        s += "----------------------------------------\n"
        return s


class EuroSciVoc(GenericVocabulary):
    def __init__(self, df: pd.DataFrame):
        super().__init__("EuroSciVoc", "EuroSciVoc", "https://op.europa.eu/en/web/eu-vocabularies/euroscivoc")
        self.load_dataframe(df)


class GEMET(GenericVocabulary):
    def __init__(self, df: pd.DataFrame):
        super().__init__("GEMET", "GEMET", "https://www.eionet.europa.eu/gemet/")
        self.load_dataframe(df)


class GCMD(GenericVocabulary):
    def __init__(self, df: pd.DataFrame):
        super().__init__("GCMD", "GCMD Science Keywords", "https://gcmd.earthdata.nasa.gov/")
        # prefLabel already holds the full hierarchical path, e.g.
        #   "EARTH SCIENCE > SOLID EARTH > GEOMORPHIC LANDFORMS/PROCESSES > COASTAL LANDFORMS > SEA CLIFFS"
        # It used to be assembled here by walking the broader relations on every startup.
        self.load_dataframe(df)


class SeaDataNetVocabulary(GenericVocabulary):
    # Names are hardcoded here, since the title is in the RDF
    sdn_vocabs = {
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

    def __init__(self, code, df: pd.DataFrame):
        assert code in self.sdn_vocabs.keys(), f"SeaDataNetVocabulary {code} not supported"
        super().__init__(code, self.sdn_vocabs[code], f"https://vocab.nerc.ac.uk/collection/{code}/current/")
        self.load_dataframe(df)

    def validate_uri(self, uri: str) -> bool:
        """
        override validate uri to make sure that all uris are http and end with /
        """
        if uri.startswith("https://"):
            uri = uri.replace("https://", "http://")

        if not uri.endswith("/"):
            uri += "/"

        return self._validate_uri(uri)


class OSO(GenericVocabulary):
    def __init__(self, df: pd.DataFrame, platforms: pd.DataFrame, sites: pd.DataFrame, rfs: pd.DataFrame,
                 platform_metadata: dict):
        """
        :param df: SKOS concepts (uri, prefLabel) used for keyword validation
        :param platforms: platform instances (uri, label)
        :param sites: site instances (uri, label)
        :param rfs: regional facility instances (uri, label)
        :param platform_metadata: platform uri -> {"site": ..., "regional_facility": ...}, resolved upstream
                                  from the ontology instead of running a SPARQL query per platform
        """
        super().__init__("OSO", "Observatories of the Seas Ontology", "https://earthportal.eu/ontologies/OSO")
        self.platforms = platforms
        self.sites = sites
        self.rfs = rfs
        self.__platform_metadata = platform_metadata
        self.load_dataframe(df)

    def __check_element(self, df, label, column):
        assert column in ["uri", "label"], f"OSO DataFrame does not have column '{column}'"
        return label in df[column].values

    def check_platform(self, this, column):
        return self.__check_element(self.platforms, this, column)

    def check_site(self, this, column):
        return self.__check_element(self.sites, this, column)

    def check_rf(self, this, column):
        return self.__check_element(self.rfs, this, column)

    def get_uri_from_name(self, name, cls):
        assert cls in ["rfs", "sites", "platforms"]

        log = logging.getLogger()

        if cls == "rfs":
            df = self.rfs
        elif cls == "sites":
            df = self.sites
        else:
            df = self.platforms
        try:
            uri = df.loc[df["label"] == name]["uri"].values[0]
        except (KeyError, IndexError):
            log.error(f"ERROR: OSO does not have any '{cls}' with label '{name}', valid names:")
            for a in df['label'].unique():
                log.error(f"    - '{a}'")
            return ""
        return str(uri)

    def get_name_from_uri(self, uri, cls):
        assert cls in ["rfs", "sites", "platforms"]

        log = logging.getLogger()

        if cls == "rfs":
            df = self.rfs
        elif cls == "sites":
            df = self.sites
        else:
            df = self.platforms
        try:
            uri = df.loc[df["uri"] == uri]["label"].values[0]
        except (KeyError, IndexError):
            log.error(f"ERROR: OSO does not have any '{cls}' with uri '{uri}', valid uris:")
            for a in df['uri'].unique():
                log.info(f"    - '{a}'")
            return ""
        return str(uri)

    def platform_metadata(self, platform_uri: str):
        """
        Returns site name and Regional Facility name for a given platform URI.
        """
        meta = self.__platform_metadata.get(platform_uri)
        if not meta:
            return "", ""
        return meta.get("site", ""), meta.get("regional_facility", "") or None


class Keyword:
    def __init__(self, name: str, uri: str, vocab: GenericVocabulary|None):
        self.name = name
        self.uri = uri
        self.vocab_code = ""
        self.vocab_uri = ""
        self.vocab_name = ""
        self.type = "undefined"

        if not uri or not vocab:
            self.valid = False
        else:
            assert isinstance(vocab, GenericVocabulary)
            assert isinstance(name, str)
            assert isinstance(uri, str)
            self.uri = uri
            self.vocab_name = vocab.name
            self.vocab_uri = vocab.uri
            self.vocab_code = vocab.code
            self.type = self.__get_type(vocab.code)
            self.valid = True


    def __get_type(self, title):
        mapping = {
            "P02": "variable",
            "P07": "variable",
            "L05": "device",
            "L06": "platform",
            "L22": "device",
            "OSO": "infrastructure",
            "GEMET": "discipline",
            "GCMD": "discipline",
            "EuroSciVoc": "discipline",
        }
        r =  mapping.get(title, "undefined")
        if r == "undefined":
            logging.warning(f"Could not find type for '{self.name}' ({self.vocab_code})")
        return r

    def __repr__(self) -> str:
        return f"Keyword name={self.name!r}\n  uri={self.uri!r}\n  vocab='{self.vocab_name}'"


    def __bool__(self):
        return self.valid

    def __eq__(self, other) -> bool:
        # Always check if 'other' is the right type first!
        if not isinstance(other, Keyword):
            raise NotImplemented
        assert isinstance(other, Keyword), f"Cannot compare Keyword with {type(other)}"

        if not self.valid and not other.valid:
            raise ValueError("Cannot compare two invalid keywords!")

        elif not self.valid or not other.valid:
            return False
        return self.uri == other.uri