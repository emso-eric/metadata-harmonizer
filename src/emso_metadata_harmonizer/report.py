#!/usr/bin/env python3
"""
This python project connects to an ERDDAP service and ensures that all listed datasets are compliant with the EMSO
Harmonization Guidelines.

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 23/2/23
"""
import json
import os
import rich
import time

from src.emso_metadata_harmonizer.metadata.waterframe import operational_tests
from . import WaterFrame
from .erddap import ERDDAP
import pandas as pd
from .metadata import  EmsoMetadata
from .metadata.utils import threadify
from .metadata.dataset import get_netcdf_metadata
from .metadata.tests import EmsoMetadataTester


def metadata_report(target,
                    dataset_list: list=[],
                    just_list: bool=False,
                    just_print: bool=False,
                    verbose: bool = False,
                    save_metadata: str = "",
                    output: str = "",
                    report: bool = False,
                    clear: bool = False,
                    excel_table: bool = False,
                    specifications="",
                    variables=[],
                    ignore_ok=False
                    ):
    """

    :param target: ERDDAP service URL, NetCDF file or JSON metadata file
    :param datasets: List of datasets to check (by default check all of them)
    :param just_list: Just list the available datasets and exit
    :param just_print: Just pretty-print the dataset metadata
    :param verbose: Shows more info
    :param save_metadata: Save dataset's metadata into the specified folder
    :param output: file to store the report of all the datasets
    :param report: Gnerate a CSV file for every test
    :param clear: Clears the downloaded files
    param: excel_table:  prints the results in a excel compatible table
    """
    if clear:
        rich.print("Clearing downloaded files...", end="")
        EmsoMetadata.clear_downloads()
        rich.print("[green]done")
        exit()

    if not target:
        rich.print("[red]ERDDAP URL, NetCDF file or JSON file required!")
        exit()

    datasets = [
        # {"file": filename, "url": "http://my.server.com/erddap", "dataset_id": "MyDataset"}
    ]

    if target.startswith("http"):
        rich.print(f"Processing ERDDAP URL {target}")

        url, dataset_id = ERDDAP.process_url(target)
        erddap = ERDDAP(url)

        if just_list:  # If set, just list datasets and exit
            erddap_datasets = erddap.dataset_list()
            rich.print("[green]Listing datasets in ERDDAP:")
            for i in range(len(erddap_datasets)):
                rich.print(f"    {i:02d} - {erddap_datasets[i]}")
            exit()

        if dataset_id:  # Run tests on ONE dataset
            datasets.append({"file": "", "url": url, "dataset_id": dataset_id, "metadata": {}})
        else:  # test ALL datasets
            for dataset_id in erddap.dataset_list():
                datasets.append({"file": "", "url": url, "dataset_id": dataset_id, "metadata": {}})

        tasks = [(d["dataset_id"],) for d in datasets]
        t = time.time()
        datasets_metadata = threadify(tasks, erddap.dataset_metadata, max_threads=5)
        for dataset, metadata in zip(datasets, datasets_metadata):
            dataset["metadata"] = metadata


        rich.print(f"Getting metadata from ERDDDAP took {time.time() - t:.02f} seconds")

    # Processing NetCDF file
    elif target.endswith(".nc"):
        rich.print(f"Loading metadata from file {target}")
        datasets.append({
            "file": target, "url": "", "dataset_id": "", "metadata": get_netcdf_metadata(target)
        })

    if just_print:
        for d in datasets_metadata:
            rich.print(d)
            exit()

    if save_metadata:
        os.makedirs(save_metadata, exist_ok=True)
        rich.print(f"Saving datasets metadata in '{save_metadata}' folder")
        for dataset_id in datasets:
            file = os.path.join(save_metadata, f"{dataset_id}.json")
            metadata = erddap.dataset_metadata(dataset_id)
            with open(file, "w") as f:
                f.write(json.dumps(metadata, indent=2))
        exit()

    tests = EmsoMetadataTester(specifications=specifications)

    total = []
    required = []
    optional = []
    institution = []
    emso_facility = []
    dataset_id = []
    for d in datasets:
        metadata = d["metadata"]
        r = tests.validate_dataset(metadata, verbose=verbose, store_results=report, variable_filter=variables, ignore_ok=ignore_ok)
        total.append(r["total"])
        required.append(r["required"])
        optional.append(r["optional"])
        institution.append(r["institution"])
        emso_facility.append(r["emso_facility"])
        dataset_id.append(r["dataset_id"])

        print("")
        if d["file"]:
            rich.print("Load NetCDF file")
            wf = WaterFrame.from_netcdf(d["file"])
        else:
            wf = WaterFrame.from_erddap(d["url"], d["dataset_id"])
        operational_tests(wf)


    tests = pd.DataFrame(
        {
            "dataset_id": dataset_id,
            "emso_facility": emso_facility,
            "institution": institution,
            "total": total,
            "required": required,
            "optional": optional,
        })

    if output:
        rich.print(f"Storing tests results in {output}...", end="")
        tests.to_csv(output, index=False, sep="\t")
        rich.print("[green]done")



