#!/usr/bin/env python3
"""
This scripts contains some utilities to work with ERDDAP.

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 1/3/23
"""

import requests
import rich
import json



class ERDDAP:
    """
    Class that implements common functionalities to perform in ERDDAP servers
    """ 
    def __init__(self, url):
        rich.print(f"User url: {url}")
        # Getting rid of everything after the domain name
        parts = url.split("/")[:3]
        url = "/".join(parts)
        if not url.endswith("/erddap"):
            url += "/erddap"
        rich.print(f"Using url: {url}")
        self.url = url

    @staticmethod
    def get(url,  headers={"Content-Type": "application/json"}):
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            rich.print(f"[red]HTTP Error: {r.status_code}")
            rich.print(f"[red]{r.text}")
            raise ValueError("exit")
        else:
            return json.loads(r.text)

    def dataset_list(self) -> list:
        """
        Returns a list of dataset IDs
        :return: dataset list
        """
        datasets_url = self.url + "/info/index.json"
        r = self.get(datasets_url)
        datasets = {}
        columns = r["table"]["columnNames"]
        dataset_ids = []
        for row in r["table"]["rows"]:
            dataset = {}
            for i in range(len(row)):
                dataset[columns[i]] = row[i]
            dataset_id = dataset["Dataset ID"]
            if dataset_id != "allDatasets":
                datasets[dataset_id] = dataset
                dataset_ids.append(dataset["Dataset ID"])

        return dataset_ids

    def dataset_metadata(self, dataset_id):
        """
        Formats from ERDDAP's ugly and disgusting JSON format to a nice, well-structured JSON
        :param url: ERDDAP url
        :param dataset_id: ID of the dataset
        :return: a dict with the metadata well structure, like:
            {
            "global": {key:  value, ...},
            "variables": {
                var1: {key, value, ...},
                var2: {key, value, ...},
                ...
                }
            }
        """
        metadata_url = f"{self.url}/info/{dataset_id}/index.json"
        r = self.get(metadata_url)
        metadata = {
            "global": {"dataset_id": dataset_id},
            "variables": {},
            "qc": {}
        }
        for row in r["table"]["rows"]:
            # Each row is similar to: ['attribute', 'NC_GLOBAL', 'author', 'String', 'Enoc Martinez']
            # so 0 -> 'attribute' or 'variable', 1 -> parameter name, 2 -> key, 3 -> data type and 4-> value
            row_type = row[0]
            param = row[1]
            attribute_key = row[2]
            data_type = row[3]
            attribute_value = row[4]

            if row_type == "variable":
                metadata["variables"][param] = {}  # create new dict
            elif row_type == "attribute":
                if param == "NC_GLOBAL":
                    metadata["global"][attribute_key] = attribute_value  # process global attribute
                else:
                    metadata["variables"][param][attribute_key] = attribute_value  # process variable attribute
            else:
                rich.print(f"WARNING could not process row {row}")

        return metadata
