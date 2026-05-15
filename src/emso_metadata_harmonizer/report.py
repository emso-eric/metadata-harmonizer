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
import requests
import rich
import time
import pandas as pd
import logging
import os

from .metadata.waterframe import operational_tests, check_keywords
from . import WaterFrame
from .erddap import ERDDAP
from .metadata import  EmsoMetadata
from .metadata.utils import threadify
from .metadata.dataset import get_netcdf_metadata
from .metadata.tests import EmsoMetadataTester

logger = logging.getLogger("emso_metadata_harmonizer")


def metadata_report(target,
                    verbose: bool = False,
                    output: str = "",
                    specifications="",
                    variables=[],
                    ignore_ok=False,
                    keywords=False,
                    csv_folder="",
                    summary:bool = False,
                    quiet:bool = False
                    ):
    """

    :param target: ERDDAP service URL, NetCDF file or JSON metadata file
    :param output: If passed a summary of ALL datasets will be stored)
    :param specifications: use a different EMSO_Metadata_Specifications.md file (only for development)
    :param variables: process only a subset of variables
    :param ignore_ok: ignores correct lines, just print errors and warnings
    :param: csv:  store the results in a CSV file (only useful when analyzing single datasets)
    :param summary: prints a summary of all reports
    :param quiet: do not print output on the stdout
    """


    if not target:
        logger.error("ERDDAP URL, NetCDF file or JSON file required!")
        exit()

    if specifications:
        EmsoMetadata.use_custom_file(specifications)

    datasets = [
        # {"file": filename, "url": "http://my.server.com/erddap", "dataset_id": "MyDataset"}
    ]

    if target.startswith("http"):
        logger.info(f"Processing ERDDAP URL {target}")

        url, dataset_id = ERDDAP.process_url(target)
        erddap = ERDDAP(url)

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


        logger.info(f"Getting metadata from ERDDDAP took {time.time() - t:.02f} seconds")

    # Processing NetCDF file
    elif target.endswith(".nc"):
        logger.info(f"Loading metadata from file {target}")
        datasets.append({
            "file": target, "url": "", "dataset_id": "",
            "metadata": get_netcdf_metadata(target, permissive=True)
        })
    else:
        raise ValueError(f"Expected .nc file or ERDDAP url, got target='{target}' ")

    tests = EmsoMetadataTester()

    total = []
    required = []
    optional = []
    institution = []
    emso_facility = []
    dataset_id = []

    if csv_folder:
        os.makedirs(csv_folder, exist_ok=True)


    for d in datasets:
        metadata = d["metadata"]
        csv_file = ""
        if csv_folder:
            csv_file = os.path.join(csv_folder, d["dataset_id"] + ".csv")
        r = tests.validate_dataset(metadata, verbose=verbose, variable_filter=variables, ignore_ok=ignore_ok, csv=csv_file, quiet=quiet)
        total.append(r["total"])
        required.append(r["required"])
        optional.append(r["optional"])
        institution.append(r["institution"])
        emso_facility.append(r["emso_facility"])
        dataset_id.append(r["dataset_id"])

        if d["file"]:
            wf = WaterFrame.from_netcdf(d["file"], permissive=True)
        else:

            # In order to avoid the download of ALL data, take just the last 7 days of data
            try:
                date_end = pd.Timestamp(metadata["global"]["time_coverage_end"])
                data_from = date_end - pd.Timedelta(days=7)
            except KeyError:
                data_from = None
            try:
                wf = WaterFrame.from_erddap(d["url"], d["dataset_id"], data_from = data_from)
            except requests.exceptions.RequestException:
                logger.critical("Could not retrieve dataset from ERDDAP, aborting report")
                return

        optest = operational_tests(wf, quiet=quiet)

    if keywords:
        keytest = check_keywords(wf, verbose=verbose, quiet=quiet)
    else:
        keytest = "skipped"

    tests = pd.DataFrame(
        {
            "dataset_id": dataset_id,
            "emso_facility": emso_facility,
            "institution": institution,
            "total": total,
            "required": required,
            "optional": optional,
            "operational": optest,
            "keywords": keytest
        })

    if output:
        logger.info(f"Storing tests results in {output}...")
        tests.to_csv(output, index=False, sep="\t")

    if summary:
        rich.print(tests)
