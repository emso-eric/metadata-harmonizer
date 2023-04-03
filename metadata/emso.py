#!/usr/bin/env python3
"""
This script contains tools to access, download and parse Metadata stored in Markdown in a gitlab repository.

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 3/3/23
"""
import os
import urllib
import ssl
import rich
import pandas as pd
import json
import concurrent.futures as futures
import time

emso_version = "develop"
#emso_version = "v0.1"

emso_metadata_url = f"https://gitlab.emso.eu/Martinez/emso-metadata-specification/-/raw/{emso_version}/EMSO_metadata.md"
oceansites_codes_url = f"https://gitlab.emso.eu/Martinez/emso-metadata-specification/-/raw/{emso_version}/OceanSites_codes.md"
emso_codes_url = f"https://gitlab.emso.eu/Martinez/emso-metadata-specification/-/raw/{emso_version}/EMSO_codes.md"

sdn_vocab_p01 = "https://vocab.nerc.ac.uk/collection/P01/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_p02 = "https://vocab.nerc.ac.uk/collection/P02/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_p06 = "https://vocab.nerc.ac.uk/collection/P06/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_p07 = "https://vocab.nerc.ac.uk/collection/P07/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_l05 = "https://vocab.nerc.ac.uk/collection/L05/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_l06 = "https://vocab.nerc.ac.uk/collection/L06/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_l22 = "https://vocab.nerc.ac.uk/collection/L22/current/?_profile=nvs&_mediatype=application/ld+json"
sdn_vocab_l35 = "https://vocab.nerc.ac.uk/collection/L35/current/?_profile=nvs&_mediatype=application/ld+json"
# standard_names = "https://vocab.nerc.ac.uk/standard_name/?_profile=nvs&_mediatype=application/ld+json"

edmo_codes = "https://edmo.seadatanet.org/sparql/sparql?query=SELECT%20%3Fs%20%3Fp%20%3Fo%20WHERE%20%7B%20%0D%0A%0" \
             "9%3Fs%20%3Fp%20%3Fo%20%0D%0A%7D%20LIMIT%201000000&accept=application%2Fjson"

spdx_licenses_github = "https://raw.githubusercontent.com/spdx/license-list-data/main/licenses.md"



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

            for header in headers:
                table[header] = []

            in_table = True
            rich.print(f"parsing Markdown table [cyan]'{title}'[/cyan]...", end="")

        elif in_table and not line.startswith("|"):  # end of the table
            in_table = False
            tables[title] = pd.DataFrame(table)  # store the metadata as a DataFrame
            rich.print("[green]done")

        elif line.startswith("|---"):  # skip the title and body separator (|----|---|---|)
            continue

        elif line.startswith("|"):  # process the row
            if not line.endswith("|"):
                line += "|"  # fix tables not properly formatted
            fields = [f.strip() for f in line.split("|")[1:-1]]
            for i in range(len(fields)):
                if fields[i] in ["false", "False"]:
                    table[headers[i]].append(False)
                elif fields[i] in ["true", "True"]:
                    table[headers[i]].append(True)
                else:
                    table[headers[i]].append(fields[i])
    return tables


def __threadify_index_handler(index, handler, args):
    """
    This function adds the index to the return of the handler function. Useful to sort the results of a
    multi-threaded operation
    :param index: index to be returned
    :param handler: function handler to be called
    :param args: list with arguments of the function handler
    :return: tuple with (index, xxx) where xxx is whatever the handler function returned
    """
    result = handler(*args)  # call the handler
    return index, result  # add index to the result


def threadify(arg_list, handler, max_threads=10, text: str = "progress..."):
    """
    Splits a repetitive task into several threads
    :param arg_list: each element in the list will crate a thread and its contents passed to the handler
    :param handler: function to be invoked by every thread
    :param max_threads: Max threads to be launched at once
    :return: a list with the results (ordered as arg_list)
    """
    index = 0  # thread index
    with futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        threads = []  # empty thread list
        results = []  # empty list of thread results
        for args in arg_list:
            # submit tasks to the executor and append the tasks to the thread list
            threads.append(executor.submit(__threadify_index_handler, index, handler, args))
            index += 1

        # wait for all threads to end
        with rich.progress.Progress() as progress:  # Use Progress() to show a nice progress bar
            task = progress.add_task(text, total=index)
            for future in futures.as_completed(threads):
                future_result = future.result()  # result of the handler
                results.append(future_result)
                progress.update(task, advance=1)

        # sort the results by the index added by __threadify_index_handler
        sorted_results = sorted(results, key=lambda a: a[0])

        final_results = []  # create a new array without indexes
        for result in sorted_results:
            final_results.append(result[1])
        return final_results



def download_files(tasks, force_download=False):
    if len(tasks) == 1:
        return None

    rich.print("Downloading files...")
    args = []
    for url, file, name in tasks:
        if os.path.isfile(file) and not force_download:
            rich.print(f"    [dark_grey]{name} already downloaded")
        else:
            rich.print(f"    downloading [cyan]'{name}'[/cyan]...")
            args.append((url, file))

    threadify(args, urllib.request.urlretrieve)


def get_sdn_jsonld_ids(file):
    with open(file, encoding="utf-8") as f:
        data = json.load(f)
    ids = []
    for element in data["@graph"]:
        if "identifier" in element.keys():
            ids.append(element["identifier"])
    return ids


def get_sdn_jsonld_pref_label(file):
    with open(file, encoding="utf-8") as f:
        data = json.load(f)

    names = []
    for element in data["@graph"][1:]:
        if "prefLabel" in element.keys() and "@value" in element["prefLabel"].keys():
            names.append(element["prefLabel"]["@value"])
    return names


def get_sdn_jsonld_uri(file):
    with open(file, encoding="utf-8") as f:
        data = json.load(f)

    names = []
    for element in data["@graph"][1:]:
        if "@id" in element.keys():
            names.append(element["@id"])
    return names


def get_edmo_codes(file):
    with open(file, encoding="utf-8") as f:
        data = json.load(f)

    codes = []
    for element in data["results"]["bindings"]:
        try:
            code = element["s"]["value"]
            code = int(code.split("/")[-1])
            if code not in codes:
                codes.append(code)
        except KeyError:
            continue

    codes = sorted(codes)
    return codes


class EmsoMetadata:
    def __init__(self, force_update=False):
        self.__folder = ".emso"
        os.makedirs(".emso", exist_ok=True)  # create a conf dir to store Markdown and other stuff
        ssl._create_default_https_context = ssl._create_unverified_context

        emso_metadata_file = os.path.join(self.__folder, "EMSO_metadata.md")
        oceansites_file = os.path.join(self.__folder, "OceanSites_codes.md")
        emso_sites_file = os.path.join(self.__folder, "EMSO_codes.md")
        sdn_vocab_p01_file = os.path.join(self.__folder, "sdn_vocab_p01.json")
        sdn_vocab_p02_file = os.path.join(self.__folder, "sdn_vocab_p02.json")
        sdn_vocab_p06_file = os.path.join(self.__folder, "sdn_vocab_p06.json")
        sdn_vocab_p07_file = os.path.join(self.__folder, "sdn_vocab_p07.json")
        sdn_vocab_l05_file = os.path.join(self.__folder, "sdn_vocab_l05.json")
        sdn_vocab_l06_file = os.path.join(self.__folder, "sdn_vocab_l06.json")
        sdn_vocab_l22_file = os.path.join(self.__folder, "sdn_vocab_l22.json")
        sdn_vocab_l35_file = os.path.join(self.__folder, "sdn_vocab_l35.json")
        edmo_codes_file = os.path.join(self.__folder, "edmo_codes.json")
        spdx_licenses_file = os.path.join(self.__folder, "spdx_licenses.md")

        tasks = [
            [emso_metadata_url, emso_metadata_file, "EMSO metadata"],
            [oceansites_codes_url, oceansites_file, "OceanSites"],
            [emso_codes_url, emso_sites_file, "EMSO codes"],
            [sdn_vocab_p01, sdn_vocab_p01_file, "SDN Vocab P01"],
            [sdn_vocab_p02, sdn_vocab_p02_file, "SDN Vocab P02"],
            [sdn_vocab_p06, sdn_vocab_p06_file, "SDN Vocab P06"],
            [sdn_vocab_p07, sdn_vocab_p07_file, "SDN Vocab P07"],
            [sdn_vocab_l05, sdn_vocab_l05_file, "SDN Vocab L05"],
            [sdn_vocab_l06, sdn_vocab_l06_file, "SDN Vocab L06"],
            [sdn_vocab_l22, sdn_vocab_l22_file, "SDN Vocab L22"],
            [sdn_vocab_l35, sdn_vocab_l35_file, "SDN Vocab L35"],
            [edmo_codes, edmo_codes_file, "EDMO codes"],
            [spdx_licenses_github, spdx_licenses_file, "spdx licenses"]
        ]

        download_files(tasks)

        tables = process_markdown_file(emso_metadata_file)
        self.global_attr = tables["Global Attributes"]
        self.variable_attr = tables["Variable Attributes"]
        self.qc_attr = tables["Quality Control Attributes"]

        tables = process_markdown_file(oceansites_file)
        self.oceansites_sensor_mount = list(tables["Sensor Mount"]["sensor_mount"].values)
        self.oceansites_sensor_orientation = list(tables["Sensor Orientation"]["sensor_orientation"].values)
        self.oceansites_data_modes = list(tables["Data Modes"]["Value"].values)
        self.oceansites_data_types = list(tables["Data Types"]["Data type"].values)

        tables = process_markdown_file(emso_sites_file)
        self.emso_regional_facilities = list(tables["EMSO Regional Facilities"]["EMSO Regional Facilities"].values)
        self.emso_sites = list(tables["EMSO Sites"]["EMSO Site"].values)

        rich.print("Loading spdx licenses...")
        tables = process_markdown_file(spdx_licenses_file)
        t = tables["Licenses with Short Idenifiers"]
        # remove extra '[' ']' in license identifiers
        new_ids = [value.replace("[", "").replace("]", "") for value in t["Short Identifier"]]
        self.spdx_license_names = new_ids
        self.spdx_license_uris = [f"https://spdx.org/licenses/{lic}" for lic in self.spdx_license_names]

        rich.print("Loading SeaDataNet vocabularies...")
        sdn_vocabs = {
            "P01": sdn_vocab_p01_file,
            "P02": sdn_vocab_p02_file,
            "P06": sdn_vocab_p06_file,
            "P07": sdn_vocab_p07_file,
            "L05": sdn_vocab_l05_file,
            "L06": sdn_vocab_l06_file,
            "L22": sdn_vocab_l22_file,
            "L35": sdn_vocab_l35_file
        }

        self.sdn_vocabs_ids = {}
        self.sdn_vocabs_pref_label = {}
        self.sdn_vocabs_uris = {}

        t = time.time()
        # Process raw SeaDataNet JSON-ld files and store them sliced in short JSON files
        for vocab, filename in sdn_vocabs.items():
            preflabel = os.path.join(self.__folder, f"{vocab}_sdn_pref_label.json")
            uris = os.path.join(self.__folder, f"{vocab}_sdn_uris.json")
            urns = os.path.join(self.__folder, f"{vocab}_sdn_urn.json")

            # Process and store prefered labels
            if not os.path.exists(preflabel):
                self.sdn_vocabs_pref_label[vocab] = get_sdn_jsonld_pref_label(filename)
                with open(preflabel, "w") as f:
                    f.write(json.dumps(self.sdn_vocabs_pref_label[vocab]))

            # Process and store URNs (or identifiers)
            if not os.path.exists(uris):
                with open(urns, "w") as f:
                    self.sdn_vocabs_ids[vocab] = get_sdn_jsonld_ids(filename)
                    f.write(json.dumps(self.sdn_vocabs_ids[vocab]))

            # Process and store URIs
            if not os.path.exists(uris):
                with open(uris, "w") as f:
                    self.sdn_vocabs_uris[vocab] = get_sdn_jsonld_uri(filename)
                    f.write(json.dumps(self.sdn_vocabs_uris[vocab]))
        rich.print(f"[purple]Slice and store took {time.time() - t:.02f} seconds")

        t = time.time()
        for vocab, _ in sdn_vocabs.items():
            preflabel = os.path.join(self.__folder, f"{vocab}_sdn_pref_label.json")
            urns = os.path.join(self.__folder, f"{vocab}_sdn_urn.json")
            uris = os.path.join(self.__folder, f"{vocab}_sdn_uris.json")
            with open(preflabel) as f:
                self.sdn_vocabs_pref_label[vocab] = json.load(f)
            with open(urns) as f:
                self.sdn_vocabs_ids[vocab] = json.load(f)
            with open(uris) as f:
                self.sdn_vocabs_uris[vocab] = json.load(f)
        rich.print(f"[purple]Load SDN prefered labels, URIs and Identifiers took {time.time() - t:.02f} seconds")

        edmo_file = os.path.join(self.__folder, f"edmo_codes_sliced.json")
        if not os.path.exists(edmo_file):
            self.edmo_codes = get_edmo_codes(edmo_codes_file)
            with open(edmo_file, "w") as f:
                f.write(json.dumps(self.edmo_codes))
        else:
            with open(edmo_file) as f:
                self.edmo_codes = json.load(f)
        rich.print(f"[purple]Load EDMO codes took {time.time() - t:.02f} seconds")

    @staticmethod
    def clear_downloads():
        """
        Clears all files in .emso folder
        """
        files = os.listdir(".emso")
        for f in files:
            if os.path.isfile(f):
                os.remove(os.path.join(".emso", f))

