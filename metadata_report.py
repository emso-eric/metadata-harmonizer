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
    if not datasets:  # if list is empty use them all
        datasets = erddap.dataset_list()

    if args.print:
        for d in datasets:
            rich.print(erddap.datasetet_metadata(d))
            exit()

    tests = ErddapTester()

    for dataset_id in datasets:
        dataset_metadata = erddap.datasetet_metadata(dataset_id)
        tests.validate_dataset(dataset_metadata)
        input("press key to analyze next dataset...\n")


