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
import rich
import pandas as pd
from .metadata.autofill import expand_minmeta, autofill_waterframe
from .metadata.dataset import add_coordinates, ensure_coordinates, update_waterframe_metadata, export_to_netcdf, \
    load_data, df_to_wf
from .metadata.merge import merge_waterframes
from .metadata.minmeta import generate_min_meta_template, load_min_meta, load_full_meta, generate_full_metadata
from .metadata import EmsoMetadata
import copy


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
    Merge data fiiles and metadata files into a NetCDF dataset according to EMSO specs. If provided, depths, lats and
    longs will be added to the dataset as dimensions.
    """

    if emso_metadata:
        emso = emso_metadata
    else:
        emso = EmsoMetadata()

    waterframes = []
    for i in range(len(data_list)):
        data = data_list[i]
        metadata = metadata_list[i]

        if type(data) is str:
            wf = load_data(data)
        elif type(data) is pd.DataFrame:
            wf = df_to_wf(data)
        else:
            raise ValueError(f"Data must be a file or DataFrame, got '{type(data)}'")

        if type(metadata) not in [str, dict]:
            raise ValueError(f"Expected str or dict, got '{type(data)}'")

        # If metadata is dict, assume it as minimal
        if type(metadata) is dict:
            minimal_metadata = True
        elif type(metadata) is str and metadata.endswith(".min.json"):
            minimal_metadata = True
            wf.metadata["$minmeta"] = metadata
        elif type(metadata) is str and metadata.endswith(".full.json") or type(metadata):
            minimal_metadata = False
        else:
            raise ValueError("Expected metadata file with extension .full.json or .min.json!")

        if type(metadata) is str:
            with open(metadata) as f:
                metadata = json.load(f)

        # Create deep copy of the metadata
        metadata = copy.deepcopy(metadata)
        if minimal_metadata:
            minmeta = load_min_meta(wf, metadata, emso)

            if "coordinates" in minmeta.keys():
                lat = minmeta["coordinates"]["latitude"]
                lon = minmeta["coordinates"]["longitude"]
                depth = minmeta["coordinates"]["depth"]
                wf = add_coordinates(wf, lat, lon, depth)

            ensure_coordinates(wf)  # make sure that all coordinates are set
            metadata = expand_minmeta(wf, minmeta, emso)

        else:
            rich.print(f"Loading a full metadata file {metadata}...")
            metadata = load_full_meta(wf, metadata)
        wf = update_waterframe_metadata(wf, metadata)
        waterframes.append(wf)
    return waterframes


def generate_dataset(data: list, metadata: list, generate: bool = False, autofill: bool = False, output: str = "",
                     clear: bool = False, emso_metadata=None) -> str:
    wf = None
    if clear:
        rich.print("Clearing downloaded files...", end="")
        EmsoMetadata.clear_downloads()
        rich.print("[green]done")
        exit()

    if generate and metadata:
        raise ValueError("--metadata and --generate cannot be used at the same time!")

    if not generate and not metadata and not autofill:
        raise ValueError("--metadata OR --generate OR --autofill option ust be used!")

    # If metadata and generate
    if generate:
        rich.print("[blue]Generating metadata templates...")
        generate_metadata(data, generate)
        exit()

    if metadata:
        waterframes = generate_datasets(data, metadata, emso_metadata=emso_metadata)

        # If ALL water frames are empty we have nothing else to do, just exit
        some_data = False
        for wf in waterframes:
            if not wf.data.empty:
                some_data = True
        if not some_data:
            rich.print("[red]There is not data in the dataframes! exit")
            exit(0)
        wf = merge_waterframes(waterframes)

    if autofill:
        if len(data) > 1:
            raise ValueError("Only one data file expected!")
        filename = data[0]
        wf = load_data(filename)
        wf = autofill_waterframe(wf)

    if output:
        export_to_netcdf(wf, output)

    if not wf:
        if len(data) > 1:
            raise ValueError("Only one data file expected!")
        filename = data[0]
        wf = load_data(filename)

    if output:
        return output
