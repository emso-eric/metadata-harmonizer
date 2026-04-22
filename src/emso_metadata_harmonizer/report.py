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
import rich
import time
import pandas as pd
import logging

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
                    csv=""
                    ):
    """

    :param target: ERDDAP service URL, NetCDF file or JSON metadata file
    :param output: If passed a summary of ALL datasets will be stored)
    :param specifications: use a different EMSO_Metadata_Specifications.md file (only for development)
    :param variables: process only a subset of variables
    :param ignore_ok: do not print correct lines, reduces the output
    param: csv:  store the results in a CSV file (only useful when analyzing single datasets)
    """


    if not target:
        logger.error("ERDDAP URL, NetCDF file or JSON file required!")
        exit()

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
            "file": target, "url": "", "dataset_id": "", "metadata": get_netcdf_metadata(target, permissive=True)
        })
    else:
        raise ValueError(f"Expected .nc file or ERDDAP url, got target='{target}' ")

    tests = EmsoMetadataTester(specifications=specifications)

    total = []
    required = []
    optional = []
    institution = []
    emso_facility = []
    dataset_id = []
    if len(datasets) > 1 and csv:
        logger.warning("CSV reports will be overwritten if multiple datasets are specified!")
    elif csv:
        logger.info(f"Storing tests results in {csv}...")

    for d in datasets:
        metadata = d["metadata"]
        r = tests.validate_dataset(metadata, verbose=verbose, variable_filter=variables, ignore_ok=ignore_ok, csv=csv)
        total.append(r["total"])
        required.append(r["required"])
        optional.append(r["optional"])
        institution.append(r["institution"])
        emso_facility.append(r["emso_facility"])
        dataset_id.append(r["dataset_id"])

        if d["file"]:
            wf = WaterFrame.from_netcdf(d["file"], permissive=True)
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
    if keywords:
        check_keywords(wf, verbose=verbose)



    if output:
        logger.info(f"Storing tests results in {output}...")
        tests.to_csv(output, index=False, sep="\t")
