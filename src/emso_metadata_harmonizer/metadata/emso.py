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
import time
import requests
import pandas as pd
import json
from rdflib import Graph
import rich
from .keywords import GEMET, GCMD, SeadatanetKeyword, EuroSciVoc
from .utils import download_files, get_file_list, download_file, assert_type, assert_url, get_file_md5
from .oso import OSO

emso_version = "develop"

log = logging.getLogger("emso_metadata_harmonizer")

metadata_specifications_resources = f"https://raw.githubusercontent.com/emso-eric/emso-metadata-specifications/refs/heads/{emso_version}/external-resources/resources.json"

spdx_licenses_github = "https://raw.githubusercontent.com/spdx/license-list-data/main/licenses.md"

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





def download_resource(data):
    """
    Download the resources in data, possible keys are
    """
    data = data.copy()
    for key, url in data.items():
        try:
            filename = url.split("external-resources/")[1]
            os.makedirs(os.path.dirname(filename), exist_ok=True)
        except IndexError:
            # No subfolders
            filename = url.split("/")[-1]

        if key != "hash":  # Get all elements except the hash
            log.info(f"    downloading to {filename}...")
            download_file(url, filename)

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


def update_external_resources(resource_url: str, resource_file: str):
    """
    Download resources in remote if hash doesn't match with local resources
    """
    log = logging.getLogger()
    assert_type(resource_url, str)
    assert_type(resource_file, str)
    assert_url(resource_url)
    local = {}

    log.debug("Starting update_external_resources...")

    # Download local resource file
    if os.path.exists(resource_file):
        with open(resource_file) as f:
            local = json.load(f)
    else:
        log.debug(f"local file {resource_file} does not exist!")

    # if there is no resource file or
    if not os.path.exists(resource_file) or time.time() - os.path.getmtime(resource_file) > 24*3600:
        log.info("Downloading resources.json remote file...")
        remote = requests.get(resource_url).json()

        for key, rmt_resource in remote.items():
            remote_hash = rmt_resource["hash"]
            try:
                local_hash = local[key]["hash"]
            except KeyError:
                local_hash = None

            if local_hash == remote_hash:
                log.debug(f"    {key} is up to date")
                continue
            else:
                log.debug(f"Resource {key} hash do not match local='{local_hash}' remote='{remote_hash}'")

            # At this point, we need to download all files in this resource
            local[key] = {"hash": remote_hash}
            for name, url in rmt_resource.items():
                if name == "hash":
                    continue

                if "external-resources/" in url:
                    filename = os.path.join(".emso", url.split("external-resources/")[-1])
                else:
                    filename = os.path.join(".emso", url.split("/")[-1])

                log.debug(f"    downloading {key}:{name} to {filename}...")
                download_file(url, filename)

                local[key][name] = filename

            with open(os.path.join(".emso", "resources.json"), "w") as f:
                json.dump(local, f, indent=2)

    else:
        log.info("No need to update resources.json")
        with open(resource_file) as f:
            local = json.load(f)  # just load local resources file

    return local


class KeywordValidator:
    def __init__(self, oso: OSO):
        gcmd = GCMD()
        euroscivoc = EuroSciVoc()
        gemet = GEMET()
        P02 = SeadatanetKeyword(os.path.join(".emso", "sdn", "P02.csv"))
        L05 = SeadatanetKeyword(os.path.join(".emso", "sdn", "L05.csv"))
        L06 = SeadatanetKeyword(os.path.join(".emso", "sdn", "L06.csv"))
        L22 = SeadatanetKeyword(os.path.join(".emso", "sdn", "L22.csv"))
        P07 = SeadatanetKeyword(os.path.join(".emso", "sdn", "P07.csv"))

        self.vocabularies = [
            gcmd,
            euroscivoc,
            gemet,
            P02,
            L05,
            L06,
            L22,
            P07,
            oso
        ]

        self.used_vocabularies = []  # list of the vocabularies used in the validation
        self.used_vocabularies_uris = []  # list of the vocabularies used in the validation

    def validate_term(self, term: str):
        assert isinstance(term, str), f"Expected string, got {type(term)}"

        # Check term against ALL vocabularies
        g_perfect_match = False
        g_partial_match = False
        perfect_match_vocabs = []  # vocabularies with perfect match
        partial_match_vocabs = []  # vocabularies with partial match
        for vocab in self.vocabularies:
            perfect_match, partial_match = vocab.validate_term(term)
            if perfect_match:
                g_perfect_match = True
                perfect_match_vocabs.append(vocab.name)
                if vocab.name not in self.used_vocabularies:
                    self.used_vocabularies.append(vocab.name)
                    self.used_vocabularies_uris.append(vocab.uri)
            elif partial_match and not g_perfect_match:
                g_partial_match = True
                partial_match_vocabs.append(vocab.name)
                if vocab.name not in self.used_vocabularies:
                    self.used_vocabularies.append(vocab.name)
                if vocab.uri not in self.used_vocabularies_uris:
                    self.used_vocabularies_uris.append(vocab.uri)

        v = perfect_match_vocabs
        if len(perfect_match_vocabs) == 0 and len(partial_match_vocabs) > 0:
            v = partial_match_vocabs
        return g_perfect_match, g_partial_match, v

    def reset_vocabularies(self):
        self.used_vocabularies = []
        self.used_vocabularies_uris = []

    def get_vocabularies(self, term_list: list):
        self.reset_vocabularies()
        for term in term_list:
            self.validate_term(term)
        return self.used_vocabularies, self.used_vocabularies_uris


class EmsoMetadata:
    def __init__(self, force_update=False, specifications=""):
        log.info("Loading EMSO Metadata resources...")
        os.makedirs(".emso", exist_ok=True)  # create a conf dir to store Markdown and other stuff
        # previous_wdir = os.getcwd()
        # os.chdir(".emso")

        self.local_resources = {}

        __resources_file = os.path.join(".emso", "resources.json")

        self.local_resources = update_external_resources(metadata_specifications_resources, __resources_file)


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

        log.info(f"Loading EMSO metadata resources:")

        # ==== Load all SDN vocabularies ==== #
        for vocab in self.sdn_vocabs.keys():
            log.debug(f"    loading SDN vocabulary {vocab}")
            df = pd.read_csv(self.local_resources[vocab]["csv"])
            self.sdn_vocabs[vocab] = df
            self.sdn_vocabs_narrower[vocab] = load_json(self.local_resources[vocab]["narrower"])
            self.sdn_vocabs_broader[vocab] = load_json(self.local_resources[vocab]["broader"])
            self.sdn_vocabs_related[vocab] = load_json(self.local_resources[vocab]["related"])
            self.sdn_vocabs_pref_label[vocab] = df["prefLabel"].values
            self.sdn_vocabs_alt_label[vocab] = df["altLabel"].values
            self.sdn_vocabs_ids[vocab] = df["id"].values
            self.sdn_vocabs_uris[vocab] = df["uri"].values


        # ==== Load Copernicus Variables ==== #
        log.debug(f"    loading Copernicus Parameters")
        tables = process_markdown_file(self.local_resources["Copernicus Parameters"]["md"])

        self.copernicus_variables = tables["Copernicus variables"]["variable name"].to_list()
        log.debug(f"    loading EDMO codes")
        self.edmo_codes = pd.read_csv(self.local_resources["EDMO"]["csv"])

        emso_metadata_file = os.path.join(".emso", "EMSO_Metadata_Specifications.md")
        oceansites_file = os.path.join(".emso", "oceansites", "OceanSites_codes.md")
        datacite_codes_file = os.path.join(".emso", "datacite", "DataCite_codes.md")

        spdx_licenses_file = os.path.join(".emso", "spdx_licenses.md")

        dwc_terms_file = os.path.join(".emso", "dwc_terms.csv")
        oso_ontology_file = os.path.join(".emso", "oso.ttl")

        tasks = [
            [spdx_licenses_github, spdx_licenses_file, "spdx licenses"],
            [dwc_terms_url, dwc_terms_file, "DwC terms"],
            [oso_ontology_url, oso_ontology_file, "OSO"]
        ]

        if specifications:
            log.warning("Using custom specifications file: {specifications}")
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
        self.oceansites_param_codes = tables["Variable Names"]["Parameter"].to_list()

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

        # Convert P02 IDs to 4-letter codes
        self.sdn_p02_names = [code.split(":")[-1] for code in self.sdn_vocabs_ids["P02"]]
        self.oso = OSO(oso_ontology_file)
        self.keywords = KeywordValidator(self.oso)

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
