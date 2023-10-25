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
from argparse import ArgumentParser
import rich
import time
from erddap import ERDDAP
import pandas as pd
from metadata import EmsoMetadata, EmsoMetadataTester, get_netcdf_metadata
from metadata.utils import threadify, download_files

if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument("target", type=str, help="ERDDAP service URL, NetCDF file or JSON metadata file", default="", nargs='?')
    argparser.add_argument("-d", "--datasets", type=str, help="List of datasets to check", nargs="+", default=[])
    argparser.add_argument("-l", "--list", action="store_true", help="List dataset in ERDDAP and exit")
    argparser.add_argument("-p", "--print", action="store_true", help="Just pretty-print the metadata")
    argparser.add_argument("-v", "--verbose", action="store_true", help="Shows more info")
    argparser.add_argument("-s", "--save-metadata", type=str, help="Save dataset's metadata into the specified folder",
                           default="")
    argparser.add_argument("-o", "--output", type=str, help="file to store the report of all the datasets", default="")
    argparser.add_argument("-r", "--report", action="store_true", help="Generate a CSV file for every test")
    argparser.add_argument("-c", "--clear", action="store_true", help="Clears downloaded files")
    argparser.add_argument("-t", "--table", action="store_true", help="prints the results in excel compatible table")

    args = argparser.parse_args()

    if args.clear:
        rich.print("Clearing downloaded files...", end="")
        EmsoMetadata.clear_downloads()
        rich.print("[green]done")
        exit()

    if not args.target:
        rich.print("[red]ERDDAP URL, NetCDF file or JSON file required!")
        exit()

    if args.target.startswith("http"):
        # Assuming ERDDAP service
        erddap = ERDDAP(args.target)
        datasets = args.datasets
        if not datasets:  # If a list of datasets is not provided, use all datasets in the service
            datasets = erddap.dataset_list()

        if args.list:  # If set, just list datasets and exit
            datasets = erddap.dataset_list()
            rich.print("[green]Listing datasets in ERDDAP:")
            for i in range(len(datasets)):
                rich.print(f"    {i:02d} - {datasets[i]}")
            exit()

        # Get all Metadata from all datasets
        t = time.time()
        tasks = [(dataset_id,) for dataset_id in datasets]
        datasets_metadata = threadify(tasks, erddap.dataset_metadata, text="Getting metadata from ERDDAP...", max_threads=5)
        rich.print(f"Getting metadata from ERDDDAP took {time.time() - t:.02f} seconds")

    # Processing NetCDF file
    elif args.target.endswith(".nc"):
        rich.print(f"Loading metadata from file {args.target}")
        metadata = get_netcdf_metadata(args.target)
        datasets_metadata = [metadata]

    # Processing JSON file
    elif args.target.endswith(".json"):
        rich.print(f"Loading metadata from file {args.target}")
        with open(args.from_file) as f:
            metadata = json.load(f)
        datasets_metadata = [metadata]  # an array with only one value
    else:
        rich.print("[red]Invalid arguments! Expected an ERDDAP url, a NetCDF file or a JSON file")

    if args.print:
        for d in datasets_metadata:
            rich.print(d)
            exit()

    if args.save_metadata:
        os.makedirs(args.save_metadata, exist_ok=True)
        rich.print(f"Saving datasets metadata in '{args.save_metadata}' folder")
        for dataset_id in datasets:
            file = os.path.join(args.save_metadata, f"{dataset_id}.json")
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
        r = tests.validate_dataset(metadata, verbose=args.verbose, store_results=args.report)
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

    if args.output:
        rich.print(f"Storing tests results in {args.output}...", end="")
        tests.to_csv(args.output, index=False, sep="\t")
        rich.print("[green]done")