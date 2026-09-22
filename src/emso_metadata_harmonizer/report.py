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
import json

from .metadata.waterframe import operational_tests, check_keywords
from . import WaterFrame
from .version import __version__
from .erddap import ERDDAP
from .metadata import  EmsoMetadata
from .metadata.utils import threadify
from .metadata.dataset import get_netcdf_metadata
from .metadata.tests import EmsoMetadataTester

logger = logging.getLogger("emso_metadata_harmonizer")

def metadata_results_to_json(df: pd.DataFrame)-> dict:
    report = {"ERRORS": {}, "WARNINGS": {}}

    for variable in df["variable"].unique():
        sdf = df[df["variable"] == variable]
        sdf = sdf[sdf["passed"] == False]

        def add_message(report: dict, t: str, varname, attribute, msg):
            if variable not in report[t].keys():
                report[t][varname] = []
            report[t][varname].append({attribute: msg})
            return report

        for attribute in sdf["attribute"].unique():
            for _, row in sdf[sdf["attribute"] == attribute].iterrows():
                message = row["message"]
                if row["value"]:
                    message += " (value='" + row["value"] + "')"
                if row["required"]:
                    report = add_message(report, "ERRORS", variable, attribute, message)
                else:
                    report = add_message(report, "WARNINGS", variable, attribute, message)

    return report


def create_json_report(dataset_id: str,
                       institution: str,
                       emso_facility: str,
                       meta_required: float,
                       meta_optional: float,
                       meta_report: dict,
                       operational_pass: bool,
                       operational_report: dict,
                       keywords_pass: bool,
                       keywords_report: dict):
    report =  {
        "dataset_id": dataset_id,
        "institution": institution,
        "emso_facility": emso_facility,
        "emso_metadata_harmonizer_version": __version__,
        "emso_metadata_specifications_version": EmsoMetadata.version(),
        "metadata": {
            "required": meta_required,
            "optional": meta_optional,
            "report": meta_report
        },
        "operational": {
            "passed": operational_pass,
            "report": operational_report
        },
        "keywords": {
            "passed": keywords_pass,
            "report": keywords_report
        }
    }
    return report


def metadata_report(target,
                    verbose: bool = False,
                    output: str = "",
                    specifications="",
                    variables=[],
                    ignore_ok=False,
                    keywords=False,
                    csv_folder="",
                    summary:bool = False,
                    quiet:bool = False,
                    clear_downloads:bool = False,
                    json_out: str = ""
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
    :param clear_downloads: clear all downloaded resources
    """

    if clear_downloads:
        EmsoMetadata.clear_downloads()

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
    oper_tests = []
    keyword_tests = []

    if csv_folder:
        os.makedirs(csv_folder, exist_ok=True)

    if json and not keywords:
        logger.warning("Forcing keywords=True for complete JSON output")
        keywords = True

    if len(datasets) != 1 and json:
        logger.error("--json option only available with one dataset!")
        raise ValueError("--json option only available with one dataset!")

    for d in datasets:
        metadata = d["metadata"]
        csv_file = ""
        if csv_folder:
            csv_file = os.path.join(csv_folder, d["dataset_id"] + ".csv")
        r, data = tests.validate_dataset(metadata, verbose=verbose, variable_filter=variables, ignore_ok=ignore_ok, csv=csv_file, quiet=quiet)

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

        operation_pass, operational_report = operational_tests(wf, quiet=quiet)
        oper_tests.append(operation_pass)

        if keywords:
            keyword_pass, keyword_report = check_keywords(wf, verbose=verbose, quiet=quiet)
        else:
            keyword_pass = False
            keyword_report = {}

        keyword_tests.append(keyword_pass)

        if json_out:
            meta_report = metadata_results_to_json(data)

            results_json = create_json_report(
                r["dataset_id"],
                r["institution"],
                r["emso_facility"],
                r["required"],
                r["optional"],
                meta_report,
                operation_pass,
                operational_report,
                keyword_pass,
                keyword_report)

            with open(json_out, "w") as f:
                json.dump(results_json, f, indent=2)


    tests = pd.DataFrame(
        {
            "dataset_id": dataset_id,
            "emso_facility": emso_facility,
            "institution": institution,
            "total": total,
            "required": required,
            "optional": optional,
            "operational": oper_tests,
            "keywords": keyword_tests
        })
    if output:
        logger.info(f"Storing tests results in {output}...")
        tests.to_csv(output, index=False, sep="\t")

    if summary:
        rich.print(tests)
