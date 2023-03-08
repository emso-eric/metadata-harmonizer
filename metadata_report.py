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
import requests
from erddap import ErddapTester, ERDDAP

from metadata import EmsoMetadata

if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument("url", type=str, help="ERDDAP URL", default="")
    argparser.add_argument("-d", "--datasets", type=str, help="List of datasets to check", nargs="+", default=[])
    argparser.add_argument("-l", "--list", action="store_true", help="List dataset in ERDDAP and exit")
    argparser.add_argument("-p", "--print", action="store_true", help="Just pretty-print the metadata")
    argparser.add_argument("-v", "--verbose", action="store_true", help="Shows more info")
    argparser.add_argument("-f", "--from-file", type=str, help="Load metadata from a file")
    argparser.add_argument("-s", "--save-metadata", type=str, help="Save dataset's metadata into the specified folder",
                           default="")

    args = argparser.parse_args()
    rich.print(f"Analyzing ERDDAP services {args.url}")

    erddap = ERDDAP(args.url)

    rich.print("Getting full list of datasets")

    if args.list:
        datasets = erddap.dataset_list()
        rich.print("[green]Listing datasets in ERDDAP:")
        for i in range(len(datasets)):
            rich.print(f"    {i:02d} - {datasets[i]}")
        exit()

    datasets = args.datasets

    if not datasets and not args.from_file:  # if list is empty use them all
        datasets = erddap.dataset_list()
    if args.save_metadata:
        os.makedirs(args.save_metadata, exist_ok=True)
        rich.print(f"Saving datasets metadata in '{args.save_metadata}' folder")
        for dataset_id in datasets:
            file = os.path.join(args.save_metadata, f"{dataset_id}.json")
            metadata = erddap.dataset_metadata(dataset_id)
            with open(file, "w") as f:
                f.write(json.dumps(metadata, indent=2))
        exit()

    if args.from_file:
        # Load metadata from a file
        rich.print(f"Loading metadata from file {args.from_file}")
        with open(args.from_file) as f:
            metadata = json.load(f)
        datasets_metadata = [metadata]  # an array with only one value
    else:
        # Get all Metadata from all datasets
        datasets_metadata = [erddap.dataset_metadata(dataset_id) for dataset_id in datasets]

    if args.print:
        for d in datasets:
            rich.print(erddap.dataset_metadata(d))
            exit()

    tests = ErddapTester()

    for i in range(len(datasets_metadata)):
        metadata = datasets_metadata[i]
        tests.validate_dataset(metadata, verbose=args.verbose)
        if i < len(datasets_metadata) - 1:
            input("press key to analyze next dataset...\n")
