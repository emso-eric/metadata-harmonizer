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
from .erddap import ERDDAP
import pandas as pd
from .metadata import EmsoMetadata
from .metadata.utils import threadify
from .metadata.dataset import get_netcdf_metadata
from .metadata.tests import EmsoMetadataTester


def metadata_report(target,
                    datasets: list=[],
                    just_list: bool=False,
                    just_print: bool=False,
                    verbose: bool = False,
                    save_metadata: str = "",
                    output: str = "",
                    report: bool = False,
                    clear: bool = False,
                    excel_table: bool = False
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

    if target.startswith("http"):
        # Assuming ERDDAP service
        erddap = ERDDAP(target)
        datasets = datasets
        if not datasets:  # If a list of datasets is not provided, use all datasets in the service
            datasets = erddap.dataset_list()

        if just_list:  # If set, just list datasets and exit
            datasets = erddap.dataset_list()
            rich.print("[green]Listing datasets in ERDDAP:")
            for i in range(len(datasets)):
                rich.print(f"    {i:02d} - {datasets[i]}")
            exit()

        # Get all Metadata from all datasets
        t = time.time()
        tasks = [(dataset_id,) for dataset_id in datasets]
        datasets_metadata = threadify(tasks, erddap.dataset_metadata, max_threads=5)
        rich.print(f"Getting metadata from ERDDDAP took {time.time() - t:.02f} seconds")

    # Processing NetCDF file
    elif target.endswith(".nc"):
        rich.print(f"Loading metadata from file {target}")
        metadata = get_netcdf_metadata(target)
        datasets_metadata = [metadata]

    # Processing JSON file
    elif target.endswith(".json"):
        rich.print(f"Loading metadata from file {target}")
        with open(target) as f:
            metadata = json.load(f)
        datasets_metadata = [metadata]  # an array with only one value
    else:
        rich.print("[red]Invalid arguments! Expected an ERDDAP url, a NetCDF file or a JSON file")

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

    tests = EmsoMetadataTester()

    total = []
    required = []
    optional = []
    institution = []
    emso_facility = []
    dataset_id = []
    for i in range(len(datasets_metadata)):
        metadata = datasets_metadata[i]
        r = tests.validate_dataset(metadata, verbose=verbose, store_results=report)
        total.append(r["total"])
        required.append(r["required"])
        optional.append(r["optional"])
        institution.append(r["institution"])
        emso_facility.append(r["emso_facility"])
        dataset_id.append(r["dataset_id"])

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


