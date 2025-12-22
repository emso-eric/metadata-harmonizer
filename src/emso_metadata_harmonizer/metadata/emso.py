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
import os
import ssl
import requests
import rich
import pandas as pd
import json
from .utils import download_files, get_file_list, download_file
from rdflib import Graph

emso_version = "develop"

metadata_specifications_resources = "https://raw.githubusercontent.com/emso-eric/emso-metadata-specifications/refs/heads/develop/external-resources/resources.json"

# List of URLs
emso_metadata_url = f"https://raw.githubusercontent.com/emso-eric/emso-metadata-specifications/{emso_version}/EMSO_metadata.md"
oceansites_codes_url = f"https://raw.githubusercontent.com/emso-eric/emso-metadata-specifications/{emso_version}/OceanSites_codes.md"
emso_codes_url = f"https://raw.githubusercontent.com/emso-eric/emso-metadata-specifications/{emso_version}/EMSO_codes.md"
datacite_codes_url = f"https://raw.githubusercontent.com/emso-eric/emso-metadata-specifications/{emso_version}/DataCite_codes.md"



spdx_licenses_github = "https://raw.githubusercontent.com/spdx/license-list-data/main/licenses.md"

# Copernicus INS TAC Parameter list v3.2
copernicus_param_list = "https://archimer.ifremer.fr/doc/00422/53381/108480.xlsx"

cf_standard_name_units_url = "https://cfconventions.org/Data/cf-standard-names/90/src/cf-standard-name-table.xml"

dwc_terms_url = "https://raw.githubusercontent.com/tdwg/dwc/refs/heads/master/vocabulary/term_versions.csv"

oso_ontology_url = "https://raw.githubusercontent.com/emso-eric/oso-ontology/refs/heads/main/docs/ontology.ttl"

def process_markdown_file(file) -> (dict, dict):
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
            table[headers[i+1]].append(annotation)

    return tables



class OSO:
    def __init__(self, ttl_file):
        self.graph = Graph().parse(ttl_file)
        self.platforms = self.get_instances_as_dataframe("https://w3id.org/earthsemantics/OSO#Platform")
        self.sites = self.get_instances_as_dataframe("https://w3id.org/earthsemantics/OSO#Site")
        self.rfs = self.get_instances_as_dataframe("https://w3id.org/earthsemantics/OSO#RegionalFacility")
        self.platforms.drop_duplicates(keep="first", inplace=True)
        self.sites.drop_duplicates(keep="first", inplace=True)
        self.rfs.drop_duplicates(keep="first", inplace=True)

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
        return pd.DataFrame(data)

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
        if cls == "rfs":
            df = self.rfs
        elif cls == "sites":
            df = self.sites
        else:
            df = self.platforms
        try:
            uri = df.loc[df["label"] == name]["uri"].values[0]
        except (KeyError, IndexError):
            rich.print(f"[red]ERROR: OSO does not have any '{cls}' with label '{name}', valid names:")
            [rich.print(f"[red]    - '{a}'") for a in df['label'].unique()]
            return ""
        return str(uri)

    def get_name_from_uri(self, uri, cls):
        assert cls in ["rfs", "sites", "platforms"]
        if cls == "rfs":
            df = self.rfs
        elif cls == "sites":
            df = self.sites
        else:
            df = self.platforms
        try:
            uri = df.loc[df["uri"] == uri]["label"].values[0]
        except (KeyError, IndexError):
            rich.print(f"[red]ERROR: OSO does not have any '{cls}' with uri '{uri}', valid uris:")
            [rich.print(f"[red]    - '{a}'") for a in df['uri'].unique()]
            return ""
        return str(uri)


def download_resource(name, data):
    """
    Download the resources in data, possible keys are
    """
    rich.print(f"Downloading resource [cyan]'{name}'")
    data = data.copy()
    for key, url in data.items():
        if key == "hash": # Get all elements except the hash
            continue
        filename = url.split("external-resources/")[1]
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        rich.print(f"    downloading to [cyan]{filename}[/cyan]...", end="")
        download_file(url, filename)
        rich.print(f"[green]done!")

        # Overwrite the remote URL with the local file
        data[key] = filename
    return data


def load_json(file):
    with open(file) as f:
        doc = json.load(f)
    return doc

emso_metadata_object = None
def init_emso_metadata(force_update=False, specifications=""):
    """
    Wrapper to avoid called EmsoMetadata twice
    """
    global emso_metadata_object
    if not emso_metadata_object:
        emso_metadata_object = EmsoMetadata(force_update=force_update, specifications=specifications)

    return emso_metadata_object

class EmsoMetadata:
    def __init__(self, force_update=False, specifications=""):
        rich.print("[purple]Loading EMSO Metadata resources...")
        os.makedirs(".emso", exist_ok=True)  # create a conf dir to store Markdown and other stuff
        previous_wdir = os.getcwd()
        os.chdir(".emso")

        __resources_file = "resources.json"

        if not os.path.exists(__resources_file):
            rich.print("[purple]resources.json file not found, downloading...")
            self.local_resources = {}
        else:
            rich.print("loading cached resources.json")
            self.local_resources = load_json(__resources_file)

        # Load local resources file
        if not force_update and os.path.exists(__resources_file):
            rich.print("[purple]loading local resource files...")
            self.local_resources = load_json(__resources_file)

        # Get the remote resources list
        remote_resources = requests.get(metadata_specifications_resources).json()
        for name, remote_resource in remote_resources.items():
            if name not in self.local_resources.keys():
                rich.print(f"resources {name} not found locally, downloading from github!")
                self.local_resources[name] = download_resource(name, remote_resource)
            elif self.local_resources[name]["hash"] != remote_resource["hash"]:
                rich.print(f"resources {name} has been updated, download!")
                self.local_resources[name] = download_resource(name, remote_resource)
            else:
                rich.print(f"[grey42]no update for {name} required...")

        sdn_vocabs = ["P01", "P02", "P06", "P07", "L05", "L06", "L22", "L35"]

        self.sdn_vocabs = {}
        self.sdn_vocabs_narrower = {}
        self.sdn_vocabs_broader = {}
        self.sdn_vocabs_related = {}
        self.sdn_vocabs_pref_label = {}
        self.sdn_vocabs_alt_label = {}
        self.sdn_vocabs_ids = {}
        self.sdn_vocabs_uris = {}

        rich.print(f"[purple]Loading EMSO metadata resources:")
        # ==== Load all SDN vocabularies ==== #
        for vocab in sdn_vocabs:
            rich.print(f"    loading SDN vocabulary {vocab}")
            df = pd.read_csv(self.local_resources[vocab]["csv"])
            self.sdn_vocabs[vocab] = df
            self.sdn_vocabs_narrower[vocab] = self.local_resources[vocab]["narrower"]
            self.sdn_vocabs_broader[vocab] = self.local_resources[vocab]["broader"]
            self.sdn_vocabs_related[vocab] = self.local_resources[vocab]["related"]
            self.sdn_vocabs_pref_label[vocab] = df["prefLabel"].values
            self.sdn_vocabs_alt_label[vocab] = df["altLabel"].values
            self.sdn_vocabs_ids[vocab] = df["id"].values
            self.sdn_vocabs_uris[vocab] = df["uri"].values


        # ==== Load Copernicus Variables ==== #
        rich.print(f"    loading Copernicus Parameters")
        self.copernicus_variables = load_json(self.local_resources["Copernicus Parameters"]["json"])
        rich.print(f"    loading EDMO codes")
        self.edmo_codes = pd.read_csv(self.local_resources["EDMO"]["csv"])


        # ==== Storing current resources ==== #
        with open(__resources_file, "w") as f:
            f.write(json.dumps(self.local_resources, indent=2))

        # Return to the old working dir
        os.chdir(previous_wdir)

        emso_metadata_file = os.path.join(".emso", "EMSO_metadata.md")
        oceansites_file = os.path.join(".emso", "OceanSites_codes.md")
        emso_sites_file = os.path.join(".emso", "EMSO_codes.md")

        datacite_codes_file = os.path.join(".emso", "DataCite_codes.md")

        spdx_licenses_file = os.path.join(".emso", "spdx_licenses.md")

        dwc_terms_file = os.path.join(".emso", "dwc_terms.csv")
        oso_ontology_file = os.path.join(".emso", "oso.ttl")

        tasks = [
            [emso_metadata_url, emso_metadata_file, "EMSO metadata"],
            [oceansites_codes_url, oceansites_file, "OceanSites"],
            [emso_codes_url, emso_sites_file, "EMSO codes"],
            [datacite_codes_url, datacite_codes_file, "DataCite codes"],
            #[edmo_codes, edmo_codes_jsonld, "EDMO codes"],
            [spdx_licenses_github, spdx_licenses_file, "spdx licenses"],
            [dwc_terms_url, dwc_terms_file, "DwC terms"],
            [oso_ontology_url, oso_ontology_file, "OSO"]
        ]

        if specifications:
            rich.print(f"[yellow]WARNING: Using custom specifications file: {specifications}")
            tasks = tasks[1:]
            emso_metadata_file = specifications

        download_files(tasks)

        tables = process_markdown_file(emso_metadata_file)

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

        tables = process_markdown_file(oceansites_file)
        self.oceansites_sensor_mount = tables["Sensor Mount"]["sensor_mount"].to_list()
        self.oceansites_sensor_orientation = tables["Sensor Orientation"]["sensor_orientation"].to_list()
        self.oceansites_data_modes = tables["Data Modes"]["Value"].to_list()
        self.oceansites_data_types = tables["Data Types"]["Data type"].to_list()

        tables = process_markdown_file(emso_sites_file)
        self.emso_regional_facilities = tables["EMSO Regional Facilities"]["EMSO Regional Facilities"].to_list()
        self.emso_sites = tables["EMSO Sites"]["EMSO Site"].to_list()

        tables = process_markdown_file(datacite_codes_file)
        self.datacite_contributor_roles = tables["DataCite Contributor Type"]["Type"].to_list()

        tables = process_markdown_file(spdx_licenses_file)
        t = tables["Licenses with Short Identifiers"]

        # remove extra '[' ']' in license identifiers
        new_ids = [value.replace("[", "").replace("]", "") for value in t["Short Identifier"]]
        self.spdx_license_names = new_ids
        self.spdx_license_uris = {lic: f"https://spdx.org/licenses/{lic}" for lic in self.spdx_license_names}

        df = pd.read_csv(dwc_terms_file)
        df = df[["term_localName", "term_iri"]]
        df = df.rename(columns={"term_localName": "name", "term_iri": "uri"})
        self.dwc_terms = df


        # TODO: Move hardcoded list to OceanSITES_codes.md
        self.oceansites_param_codes = ["AIRT", "CAPH", "CDIR", "CNDC", "CSPD", "depth", "DEWT", "DOX2", "DOXY",
                                       "DOXY_TEMP", "DYNHT", "FLU2", "HCSP", "HEAT", "ISO17", "LW", "OPBS", "PCO2",
                                       "PRES", "PSAL", "RAIN", "RAIT", "RELH", "SDFA", "SRAD", "SW", "TEMP", "UCUR",
                                       "UWND", "VAVH", "VAVT", "VCUR", "VDEN", "VDIR", "VWND", "WDIR", "WSPD"]
        # Convert P02 IDs to 4-letter codes
        self.sdn_p02_names = [code.split(":")[-1] for code in self.sdn_vocabs_ids["P02"]]

        self.oso = OSO(oso_ontology_file)




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
    def harmonize_uri(uri):
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
        uri = self.harmonize_uri(uri)
        __allowed_keys = ["prefLabel", "id", "definition", "altLabel"]
        if key not in __allowed_keys:
            raise ValueError(f"Key '{key}' not valid, allowed keys: {__allowed_keys}")

        df = self.sdn_vocabs[vocab_id]
        row = df.loc[df["uri"] == uri]
        if row.empty:
            #raise LookupError(f"Could not get {key} for '{uri}' in vocab {vocab_id}")
            rich.print(f"[red]Could not get {key} for '{uri}' in vocab {vocab_id}")
            return

        return row[key].values[0]

    def get_vocab_by_uri(self, vocab_id, uri) -> (str, str, str, str):
        """
        Search in vocab <vocab_id> for the element with matching uri and return element identified by key
        :param vocab_id:
        :param uri: uri
        :returns: tuple of (uri, urn, prefLabel, altlabel)
        """
        uri = self.harmonize_uri(uri)
        df = self.sdn_vocabs[vocab_id]
        row = df.loc[df["uri"] == uri]
        if row.empty:
            raise LookupError(f"Could not find '{uri}' in vocab {vocab_id}")
        return row["uri"].values[0], row["id"].values[0], row["prefLabel"].values[0], row["altLabel"].values[0]


    def get_vocab_by_urn(self, vocab_id, urn):
        """
        Search in vocab <vocab_id> for the element with matching uri and return element identified by key
        """
        uri = self.harmonize_uri(urn)
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
        __valid_relations = ["narrower", "broader", "related"]
        uri = self.harmonize_uri(uri)

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
            rich.print(f"[red]relation {relation} for {uri} not found!")
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
        results = self.get_relations(vocab_id, uri, relation, target_vocab)
        if len(results) == 0:
            rich.print(f"[red]Could not find relation {relation} for {uri}")
            return ""
        elif len(results) != 1:
            raise LookupError(f"Expected 1 value, got {len(results)}")

        return results[0]
