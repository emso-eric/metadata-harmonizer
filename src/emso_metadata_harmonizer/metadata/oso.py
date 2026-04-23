import pandas as pd
from .keywords import KeywordList
from rdflib import Graph, Namespace, URIRef, RDFS
import logging

class OSO(KeywordList):
    def __init__(self, ttl_file):
        super().__init__()
        self.name = "Observatories of the Seas Ontology"
        self.uri = "https://earthportal.eu/ontologies/OSO"
        self.graph = Graph().parse(ttl_file)
        self.platforms = self.get_instances_as_dataframe("https://w3id.org/earthsemantics/OSO#Platform")
        self.sites = self.get_instances_as_dataframe("https://w3id.org/earthsemantics/OSO#Site")
        self.rfs = self.get_instances_as_dataframe("https://w3id.org/earthsemantics/OSO#RegionalFacility")

        self.platforms.drop_duplicates(keep="first", inplace=True)
        self.sites.drop_duplicates(keep="first", inplace=True)
        self.rfs.drop_duplicates(keep="first", inplace=True)

        self.terms = []
        for df in [self.platforms, self.sites, self.rfs]:
            self.terms += df["label"].to_list()


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

    # def platform_metadata(self, platform_uri: str):
    #     """
    #     returns site name, RF name
    #     """
    #     nsOSO = Namespace("https://w3id.org/earthsemantics/OSO#")
    #     platform = URIRef(platform_uri).split("#")[-1]
    #
    #     query = f"""
    #     PREFIX OSO: <https://w3id.org/earthsemantics/OSO#>
    #     PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    #     SELECT ?site ?label WHERE {{
    #         ?site OSO:containsPlatform OSO:{platform} .
    #         ?site skos:prefLabel ?siteName .
    #         FILTER (LANG(?siteName) = "en")
    #     }}
    #     LIMIT 1
    #     """
    #
    #     for row in self.graph.query(query):
    #         print(f"Site URI: {row.site}")
    #         print(f"English Label: {row.siteName}")
    #
    #
    #     # Define namespaces in the query
    #     for row in self.graph.query(query, initNs={'nsOSO': nsOSO, 'rdfs': RDFS}):
    #         site_uri = row.site
    #         site_label = str(row.label)
    #         print(f"Site Label: {site_label}")
    #
    #     # 2. Find the Regional Facility that contains this Site.
    #     # The property is OSO:hasSite, with domain = Regional Facility, range = Site.
    #     # So we query for (?rf OSO:hasSite <site_uri>)
    #     regional_facility_uri = None
    #     if site_uri:
    #         for rf in self.graph.subjects(predicate=nsOSO.containsSite, object=site_uri):
    #             regional_facility_uri = rf
    #             break # Assume one regional facility per site
    #     else:
    #         print("ERROR NOT site_uri")
    #
    #     return str(site_uri) if site_uri else None, str(regional_facility_uri) if regional_facility_uri else None