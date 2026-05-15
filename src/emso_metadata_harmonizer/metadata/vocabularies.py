"""
This file contains the logic to parse and build controlled vocabularies using the GenericVocabulary class. All further
vocabularies should inherit from this class.
"""
import json
import logging
import pandas as pd
import os
from rdflib import Graph
import time
import gzip
from .utils import download_file, LoggerSuperclass, BLU



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

        self.graph = None

        self.rdf_file = ""
        self.csv_file = ""

        self.broader = {}
        self.narrower = {}
        self.related = {}

        self.concept_prefix = ""

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

    def download_file(self, uri, file):
        """
        Generic download file. Override if your vocabulary needs some specific download strategy
        """
        os.makedirs(os.path.dirname(file), exist_ok=True)
        download_file(uri, file)

    def __load_csv(self, csv_file):
        assert os.path.exists(csv_file)
        # Load the parsed file (faster option)
        df = pd.read_csv(csv_file)
        assert len(df) > 0, f"CSV lenght is 0!"
        for t in ["uri", "prefLabel"]:
            assert t in df.columns, f"Column {t} not found!"

        return df["uri"].to_list(), df["prefLabel"].to_list()

    def load_vocab(self, uri,csv_file, rdf_file, query):
        t = time.time()
        uris, labels = self.__load_vocab(uri, csv_file, rdf_file, query)
        self.set_terms(labels, uris)
        self.debug(f"Load vocabulary {self.name} took {time.time() - t:.03f} secs")

    def __load_vocab(self, uri, csv_file, rdf_file, query):
        self.rdf_file = rdf_file
        self.csv_file = csv_file
        try:
            df = self.__load_csv(csv_file)
            self.debug(f"Vocab '{self.name}' loaded from local file '{csv_file}'")
            return df
        except AssertionError as e:
            self.debug(f"Could not load from {self.name} from CSV {csv_file}")

        if not os.path.exists(rdf_file):
            # If RDF file does not exist
            self.info(f"Downloading {self.name} to {rdf_file}")
            self.download_file(uri, rdf_file)

        if not self.graph:
            self.debug(f"Loading {self.name} from RDF file {rdf_file}")
            format_type = "xml"  # rdf is xml
            self.graph = Graph()
            self.graph.parse(rdf_file, format=format_type)
            self.graph = self.graph
        else:
            self.graph = self.graph

        results = self.graph.query(query)
        uris = []  # URIs
        prefs = []  # prefered Labels
        self.debug(f"{self.name} RDF query returned {len(results)} lines")
        for row in results:
            # Convert rdflib terms to strings or "None" if they don't exist
            uris.append(self.ensure_uri(row.concept))
            prefs.append(self.ensure_uri(row.prefLabel) if row.prefLabel else "")

        uris = [str(s) for s in uris]
        prefs = [str(s) for s in prefs]

        self.debug(f"Storing pre-processed CSV file for {self.name}")
        df = pd.DataFrame({"uri": uris, "prefLabel": prefs})
        df.to_csv(csv_file, index=False)
        return uris, prefs

    def ensure_uri(self, a):
        if not isinstance(a, str):
            a = str(a)

        if a.startswith("file:"):
            assert self.concept_prefix, f"concept prefix not set for vocab {self.name}"
            return self.concept_prefix + a.split("/")[-1]
        return a

    def load_relations(self, broader_file, narrower_file, related_file):
        """
        Tries to load broader / narrower / related relations from JSON files. If they do not exist, parse the RDF graph
        """
        t = time.time()
        if all([os.path.isfile(f) for f in [broader_file, narrower_file, related_file]]):
            self.__load_relations_files(broader_file, narrower_file, related_file)
            self.debug(f"{self.name} - Loading relations from JSON files took {time.time() - t:.03f} secs")
        else:
            self.__load_relations_rdf(broader_file, narrower_file, related_file)
            self.debug(f"{self.name} - Parsing relations from RDF Graph took {time.time() - t:.03f} secs")

    def __load_relations_files(self, broader_file, narrower_file, related_file):
        """
        Reads relationships from pre-processed JSON files
        """

        def read_json(file):
            with open(file, "r") as f:
                return json.load(f)

        self.broader = read_json(broader_file)
        self.narrower = read_json(narrower_file)
        self.related = read_json(related_file)

    def __load_relations_rdf(self,broader_file, narrower_file, related_file):
        """
        Load broader / narrower / related relation from RDF graph. Processes relations are then dumped into JSON files
        for faster re-use.
        """
        query = """
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT ?concept ?label ?broader ?narrower ?related
            WHERE {
                ?concept a skos:Concept .
                OPTIONAL { ?concept skos:prefLabel ?label . FILTER(lang(?label) = "en") }
                OPTIONAL { ?concept skos:broader ?broader . }
                OPTIONAL { ?concept skos:narrower ?narrower . }
                OPTIONAL { ?concept skos:related ?related . }
            }
            """
        if not self.graph:
            self.graph = Graph()
            self.graph.parse(self.rdf_file)

        results = self.graph.query(query)

        for row in results:
            c = self.ensure_uri(row.concept)
            b = self.ensure_uri(row.broader if row.broader else "")
            n = self.ensure_uri(row.narrower if row.narrower else "")
            r = self.ensure_uri(row.related if row.related else "")

            if c not in self.broader.keys():
                self.broader[c] = []
            if c not in self.narrower.keys():
                self.narrower[c] = []
            if c not in self.related.keys():
                self.related[c] = []

            if b and  b not in self.broader[c]:
                self.broader[c].append(b)
            if n and n not in self.narrower[c]:
                self.narrower[c].append(n)
            if r and r not in self.related[c]:
                self.related[c].append(r)

        def write_json(fname, data):
            with open(fname, "w") as f:
                f.write(json.dumps(data, indent=2))

        write_json(broader_file, self.broader)
        write_json(narrower_file, self.narrower)
        write_json(related_file, self.related)



    def __repr__(self):
        s = "----------------------------------------\n"
        s += f"Vocabulary: '{self.name}'\n"
        s += f"       uri: {self.uri}\n"
        s += f"     terms: {len(self.terms)}\n"
        s += "----------------------------------------\n"
        return s


class EuroSciVoc(GenericVocabulary):
    def __init__(self):
        super().__init__("EuroSciVoc", "EuroSciVoc", "https://op.europa.eu/en/web/eu-vocabularies/euroscivoc")

        download_uri  = "https://op.europa.eu/o/opportal-service/euvoc-download-handler?cellarURI=http%3A%2F%2Fpublications.europa.eu%2Fresource%2Fdistribution%2Feuroscivoc%2F20250924-0%2Frdf%2Fskos_xl%2FEuroSciVoc.rdf&fileName=EuroSciVoc.rdf"
        rdf_file = os.path.join(".emso", "keywords", "euroscivoc", "euroscivoc.rdf")
        csv_file = os.path.join(".emso", "keywords", "euroscivoc", "euroscivoc.csv")

        query = """
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

            SELECT ?concept ?prefLabel
            WHERE {
                ?concept rdf:type skos:Concept .

                # Get English Preferred Label
                OPTIONAL {
                    ?concept skosxl:prefLabel/skosxl:literalForm ?prefLabel .
                    FILTER(lang(?prefLabel) = "en")
                }
            }
            """
        self.load_vocab(download_uri, csv_file, rdf_file, query)



class GEMET(GenericVocabulary):
    def __init__(self):
        super().__init__("GEMET", "GEMET", "https://www.eionet.europa.eu/gemet/")

        download_uri  = "https://www.eionet.europa.eu/gemet/latest/gemet.rdf.gz"
        gzip_file = os.path.join(".emso", "keywords", "gemet", "gemet.rdf.gz")
        rdf_file = os.path.join(".emso", "keywords", "gemet", "gemet.rdf")
        csv_file = os.path.join(".emso", "keywords", "gemet", "gemet.csv")

        query = """
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

            SELECT DISTINCT ?concept ?prefLabel
            WHERE {
                ?concept skos:prefLabel ?prefLabel .
                FILTER(lang(?prefLabel) = "en")
                FILTER(CONTAINS(STR(?concept), "/concept/"))
            }
            ORDER BY ?prefLabel
        """
        self.load_vocab(download_uri, csv_file, rdf_file, query)

    def download_file(self, uri, file):
        """
        GEMET is downloaded as a gzip file
        """
        os.makedirs(os.path.dirname(file), exist_ok=True)
        gzip_file = ".gemet.gzip"
        self.debug(f"Downloading GEMET to GZ file {gzip_file}, this may take a while...")
        download_file(uri, gzip_file)
        self.debug(f"Uncompressing to RDF file {file}")
        with gzip.open(gzip_file, 'rt', encoding='utf-8') as f:
            with open(file, "w") as fout:
                content = f.read()
                cleaned_content = content.replace(
                    'rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime"></dcterms:created>',
                    '></dcterms:created>')
                cleaned_content = cleaned_content.replace(
                    'rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime"></dcterms:modified>',
                    '></dcterms:modified>')
                fout.write(cleaned_content)

        if os.path.exists(gzip_file):
            os.remove(gzip_file)



class GCMD(GenericVocabulary):
    def __init__(self):
        super().__init__("GCMD", "GCMD Science Keywords", "https://gcmd.earthdata.nasa.gov/")

        # When IDs are not URIs, convert them to uris by using concept_prefix + ID
        self.concept_prefix = "https://cmr.earthdata.nasa.gov/kms/concept/"

        download_uri  = [
            "https://cmr.earthdata.nasa.gov/kms/concepts/concept_scheme/sciencekeywords/?format=rdf&page_num=1&page_size=2000",
            "https://cmr.earthdata.nasa.gov/kms/concepts/concept_scheme/sciencekeywords/?format=rdf&page_num=2&page_size=2000"
        ]

        rdf_file = os.path.join(".emso", "keywords", "gcmd", "gcmd.rdf")
        csv_file = os.path.join(".emso", "keywords", "gcmd", "gcmd.csv")
        broader = os.path.join(".emso", "keywords", "gcmd", "gcmd.broader.json")
        narrower = os.path.join(".emso", "keywords", "gcmd", "gcmd.narrower.json")
        related = os.path.join(".emso", "keywords", "gcmd", "gcmd.related.json")


        query = """
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>            
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

            SELECT ?concept ?prefLabel
            WHERE {
                ?concept rdf:type skos:Concept .

                # Get English Preferred Label
                OPTIONAL {
                    ?concept skos:prefLabel ?prefLabel .
                    FILTER(lang(?prefLabel) = "en")
                }

            }
            """
        self.load_vocab(download_uri, csv_file, rdf_file, query)
        self.load_relations(broader, narrower, related)
        self.build_gcmd_hierarchy()

    def build_gcmd_hierarchy(self):
        """
        Convert from simple terms to terms containing history:
            before: "SEA CLIFFS"
             after: "EARTH SCIENCE > SOLID EARTH > GEOMORPHIC LANDFORMS/PROCESSES > COASTAL LANDFORMS > SEA CLIFFS"
        """
        new_terms = []
        t = time.time()
        for uri in self.uris:
            new_terms.append(self.build_term(uri))
        self.debug(f"Building GCMD hierarchy took {time.time() - t :.03f}")
        self.set_terms(new_terms, self.uris)


    def build_term(self, uri, previous=""):
        """
        Scans GCMD to build the full path with broader relations, like
            from "ATMOSPHERIC NITRIC ACID"
            to "ATMOSPHERE > ATMOSPHERIC CHEMISTRY > NITROGEN COMPOUNDS > ATMOSPHERIC NITRIC ACID"
        """


        label = self.label_from_uri(uri)
        if label == "Science Keywords":
            # Do not include higher level
            return previous

        # Append previous to label
        if previous:
            label = label + " > " + previous

        if len(self.broader[uri]) == 0:
            return label + previous
        elif len(self.broader[uri]) == 1:
            return self.build_term(self.broader[uri][0], label)
        else:
            raise ValueError("Unexpected multiple broader!")

    def download_file(self, uri, file):
        """
        Download GCMD file in chunks and merge them into a single RDF
        """
        os.makedirs(os.path.dirname(file), exist_ok=True)
        assert isinstance(uri, list), f"GCMD needs to be downloaded in chunks, so list is expected"
        temp_files = []
        for i, part_uri in enumerate(uri):
            temp_files.append(f".temp{i}.rdf")
            self.debug(f"{self.name} - downloading RDF part {i}")
            download_file(part_uri, temp_files[i])

        graphs = []

        for f in temp_files:
            g = Graph()
            g.parse(f, format="xml")
            graphs.append(g)
            os.remove(f)

        self.debug(f"{self.name} - merging RDF graphs")
        self.graph = graphs[0]
        for g in graphs[1:]:
            self.graph += g

        self.graph.serialize(destination=file, format="xml")


class SeaDataNetVocabulary(GenericVocabulary):

    # SeaDataNet should already be parsed
    def __init__(self, code):
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
        assert code in sdn_vocabs.keys(), f"SeaDataNetVocabulary {code} not supported"
        name = sdn_vocabs[code]

        uri = f"https://vocab.nerc.ac.uk/collection/{code}/current/"
        download_uri = f"https://vocab.nerc.ac.uk/collection/{code}/current/?_profile=nvs&_mediatype=application/rdf+xml"
        super().__init__(code, name, uri)

        csv_file = os.path.join(".emso", "sdn", f"{code}.csv")
        rdf_file = os.path.join(".emso", "sdn", f"{code}.rdf")

        query = """
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

            SELECT ?concept ?label
            WHERE {
                ?concept rdf:type skos:Concept .

                # Get the preferred label
                ?concept skos:prefLabel ?label .

                # Filter for English specifically
                FILTER(lang(?label) = "en")
            }
            ORDER BY ?label
            """
        self.load_vocab(download_uri, csv_file, rdf_file, query)

        b = os.path.join(".emso", "sdn", f"{code}.broader.json")
        n = os.path.join(".emso", "sdn", f"{code}.narrower.json")
        r = os.path.join(".emso", "sdn", f"{code}.related.json")
        self.load_relations(b, n , r)

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
    def __init__(self, ttl_file):
        super().__init__("OSO", "Observatories of the Seas Ontology", "https://earthportal.eu/ontologies/OSO")
        download_uri = "https://raw.githubusercontent.com/emso-eric/oso-ontology/refs/heads/main/OSO.ttl"
        self.graph = Graph().parse(ttl_file)
        self.platforms = self.get_instances_as_dataframe("https://w3id.org/earthsemantics/OSO#Platform")
        self.sites = self.get_instances_as_dataframe("https://w3id.org/earthsemantics/OSO#Site")
        self.rfs = self.get_instances_as_dataframe("https://w3id.org/earthsemantics/OSO#RegionalFacility")

        self.platforms.drop_duplicates(keep="first", inplace=True)
        self.sites.drop_duplicates(keep="first", inplace=True)
        self.rfs.drop_duplicates(keep="first", inplace=True)

        query = """
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        
            SELECT DISTINCT ?concept ?prefLabel
            WHERE {
                # Match any element that has a preferred label
                ?concept skos:prefLabel ?prefLabel .
                
                # Ensure we only get the English version
                FILTER (lang(?prefLabel) = "en")
            }
            ORDER BY ?prefLabel
        """
        csv_file = os.path.join(".emso", "oso", "oso.csv")
        rdf_file = os.path.join(".emso", "oso", "oso.ttl")
        self.load_vocab(download_uri, csv_file, rdf_file, query)



    def get_instances_as_dataframe(self, class_uri):
        query = f"""
            SELECT ?instance ?label
            WHERE {{
                ?instance a <{class_uri}> .
                OPTIONAL {{
                    ?instance rdfs:label ?label .
                }}
            }}
        """
        results = self.graph.query(query)
        data = [{"uri": str(row.instance), "label": str(row.label)} for row in results]
        df = pd.DataFrame(data)
        return df

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
        platform_local = platform_uri.split("#")[-1]

        query = f"""
        PREFIX OSO: <https://w3id.org/earthsemantics/OSO#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT ?site ?siteName ?rf ?rfName WHERE {{
            ?site OSO:containsPlatform OSO:{platform_local} .
            ?site skos:prefLabel ?siteName .
            OPTIONAL {{
                ?rf OSO:containsSite ?site .
                ?rf skos:prefLabel ?rfName .
                FILTER (LANG(?rfName) = "en")
            }}
            FILTER (LANG(?siteName) = "en")
        }}
        LIMIT 1
        """

        for row in self.graph.query(query):
            site_uri = str(row.site)
            site_name = str(row.siteName)
            rf_uri = str(row.rf) if row.rf else None
            rf_name = str(row.rfName) if row.rfName else None
            return site_name, rf_name

        return "", ""

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

    def __eq__(self, other):
        # Always check if 'other' is the right type first!
        if not isinstance(other, Keyword):
            return NotImplemented
        assert isinstance(other, Keyword), f"Cannot compare Keyword with {type(other)}"
        assert self.valid, f"Cannot compare invalid Keywords"
        return self.uri == other.uri