#!/usr/bin/env python3
"""

Generates NetCDF files based on CSV files and input from the user

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 13/4/23
"""
import json
import logging
import rich
import pandas as pd
from .metadata.autofill import autofill_waterframe
from .metadata.dataset import load_data
from .metadata.minmeta import generate_min_meta_template, generate_full_metadata, load_metadata
from .metadata import EmsoMetadata
from .metadata.waterframe import WaterFrame, merge_waterframes


def generate_metadata(data_files: list, folder):
    """
    Generate the metadata templates for the input file in the target folder
    """
    # If metadata and generate
    for file in data_files:
        rich.print(f"generating minimal metadata template for {file}")
        wf = load_data(file)
        if file.endswith(".csv"):  # For CSV always generate a minimal metdata file
            generate_min_meta_template(wf, folder)
        elif file.endswith(".nc"):
            generate_full_metadata(wf, folder)

    rich.print(f"[green]Please edit the following files and run the generator with the -m option!")


def generate_datasets(data_list: list, metadata_list: list, emso_metadata: EmsoMetadata):
    """
    Merge data files and metadata files into a NetCDF dataset according to EMSO specs. If provided, depths, lats and
    longs will be added to the dataset as dimensions.
    """

    assert len(metadata_list) == len(data_list), "Expected the same amount of data and metaadata elements!"
    if emso_metadata:
        emso = emso_metadata
    else:
        emso = EmsoMetadata()
    waterframes = []
    for data_file, meta_file in zip(data_list, metadata_list):
        meta = load_metadata(meta_file, emso)
        df = load_data(data_file)
        wf = WaterFrame(df, meta)
        waterframes.append(wf)
    return waterframes


def generate_dataset(data: list, metadata: list, generate: bool = False, autofill: bool = False, output: str = "",
                     clear: bool = False, emso_metadata=None) -> str:
    wf = None
    log = logging.getLogger("emh")
    if clear:
        log.info("Clearing downloaded files...")
        EmsoMetadata.clear_downloads()

    if generate and metadata:
        raise ValueError("--metadata and --generate cannot be used at the same time!")

    if not generate and not metadata and not autofill:
        raise ValueError("--metadata OR --generate OR --autofill option ust be used!")

    # If metadata and generate
    if generate:
        log.info("Generating metadata templates...")
        generate_metadata(data, generate)
        return ""

    if metadata:
        waterframes = generate_datasets(data, metadata, emso_metadata=emso_metadata)
        if all([wf.data.empty for wf in waterframes]):
            raise ValueError("All waterframes are empty!")

        wf = merge_waterframes(waterframes)

    if autofill:
        if len(data) > 1:
            raise ValueError("Only one data file expected!")
        filename = data[0]
        wf = load_data(filename)
        wf = autofill_waterframe(wf)

    if output:
        wf.to_netcdf(output)

    if not wf:
        if len(data) > 1:
            raise ValueError("Only one data file expected!")
        filename = data[0]
        wf = load_data(filename)

    if output:
        return output
