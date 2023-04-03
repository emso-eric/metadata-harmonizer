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
from erddap import ErddapTester, ERDDAP

from metadata import EmsoMetadata
from metadata.emso import threadify

if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument("url", type=str, help="ERDDAP URL", default="", nargs='?')
    argparser.add_argument("-d", "--datasets", type=str, help="List of datasets to check", nargs="+", default=[])
    argparser.add_argument("-l", "--list", action="store_true", help="List dataset in ERDDAP and exit")
    argparser.add_argument("-p", "--print", action="store_true", help="Just pretty-print the metadata")
    argparser.add_argument("-v", "--verbose", action="store_true", help="Shows more info")
    argparser.add_argument("-f", "--from-file", type=str, help="Load metadata from a file")
    argparser.add_argument("-s", "--save-metadata", type=str, help="Save dataset's metadata into the specified folder",
                           default="")
    argparser.add_argument("-c", "--clear", action="store_true", help="Clears downloaded files")

    args = argparser.parse_args()

    if args.clear:
        rich.print("Clearing downloaded files...", end="")
        EmsoMetadata.clear_downloads()
        rich.print("[green]done")
        exit()

    if not args.url:
        rich.print("[red]ERDDAP URL required!")
        exit()

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
        t = time.time()
        tasks = [(dataset_id,) for dataset_id in datasets]
        datasets_metadata = threadify(tasks, erddap.dataset_metadata, text="Getting metadata from ERDDAP...", max_threads=3)
        rich.print(f"Getting metadata took {time.time() - t:.02f} seconds")

    if args.print:
        for d in datasets:
            rich.print(erddap.dataset_metadata(d))
            exit()

    tests = ErddapTester()

    total = []
    required = []
    optional = []
    institution = []
    for i in range(len(datasets_metadata)):
        metadata = datasets_metadata[i]
        r = tests.validate_dataset(metadata, verbose=args.verbose)
        total.append(100*r["total"])
        required.append(100*r["required"])
        optional.append(100*r["optional"])
        institution.append(r["institution"])


    import pandas as pd

    tests = pd.DataFrame(
        {
            "total": total,
            "required": required,
            "optional": optional,
            "institution": institution
        })

    tests.to_csv("report.csv", index=False)
    #
    # institutions = tests["institution"].unique()
    # rich.print(institutions)
    # alltests = tests.copy()
    # for ins in institutions:
    #     tests = alltests["institution" == ins]
    #     import seaborn as sns
    #     import matplotlib.pyplot as plt
    #     sns.set(style="whitegrid")
    #
    #     fig, axd = plt.subplot_mosaic([['left', 'right'], ['bottom', 'bottom']],
    #                                   constrained_layout=True)
    #
    #
    #     ax2 = axd['left']
    #     ax3 = axd['right']
    #     ax1 = axd['bottom']
    #
    #     ax1.set_title("Total tests")
    #     ax2.set_title("Required tests")
    #     ax3.set_title("Optional tests")
    #
    #     bindwitdh=5
    #     sns.histplot(data=tests, x="total", ax=ax1, binwidth=bindwitdh)
    #     sns.histplot(data=tests, x="required", ax=ax2, binwidth=bindwitdh)
    #     sns.histplot(data=tests, x="optional", ax=ax3, binwidth=bindwitdh)
    #     ax1.set_xlim([0, 100])
    #     ax2.set_xlim([0, 100])
    #     ax3.set_xlim([0, 100])
    #
    #     [ax.set_xlabel("tests passed (%)") for ax in [ax1, ax2, ax3]]
    #     [ax.set_ylabel("number of tests") for ax in [ax1, ax2, ax3]]
    #
    #
    #
    #     import numpy as np
    #
    #     total = np.array(total)
    #     required = np.array(required)
    #     optional = np.array(optional)
    #     fig.suptitle(ins, fontsize=14)
    #
    #     print(f"total median: {np.median(total)}")
    #     print(f"total mean: {np.mean(total)}")
    # plt.show()