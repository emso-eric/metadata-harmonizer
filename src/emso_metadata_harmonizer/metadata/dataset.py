#!/usr/bin/env python3
"""

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 29/4/23
"""
from .waterframe import WaterFrame
import pandas as pd
from .constants import dimensions
import rich
import xarray as xr


# -------- Functions to handle data from CSV files -------- #
def load_csv_data(filename, sep=",") -> (pd.DataFrame, list):
    """
    Loads data from a CSV file and returns a WaterFrame
    """
    if not filename.endswith(".csv"):
        rich.print(f"[yellow]WARNING! extension of file {filename} is not '.csv', trying anyway...")

    header_lines = csv_detect_header(filename, separator=sep)
    df = pd.read_csv(filename, skiprows=header_lines, sep=sep)
    return df

def csv_detect_header(filename, separator=","):
    """
    Opens a CSV, reads the last 3 lines and extracts the number of fields. Then it goes back to the beginning and
    detects the first line which is not a header
    """
    with open(filename) as f:
        lines = f.readlines()

    if len(lines) < 3:
        # empty CSV, first line is the header
        return 0

    nfields = len(lines[-2].split(separator))
    if nfields < 2 or not (nfields == len(lines[-3].split(separator)) == len(lines[-4].split(separator))):
        raise ValueError("Could not determine number of fields")

    # loop until a first a line with nfields is found
    i = 0
    while len(lines[i].split(separator)) != nfields:
        i += 1
    return i


def load_data(file: str) -> pd.DataFrame:
    """
    Opens a CSV or NetCDF data and returns a DataFrame
    """
    if file.endswith(".csv"):
        df = load_csv_data(file)
    elif file.endswith(".nc"):
        df = nc_to_dataframe(file)
    else:
        raise ValueError("Unimplemented file format for data!")

    df["time"] = pd.to_datetime(df["time"])
    return df


def semicolon_to_list(attr: str):
    """
    Converts semi-colon separated list of items into a python list
    """
    if type(attr) == str and ";" in attr:
        return attr.split(";")
    else:
        return attr


def nc_to_dataframe(filename: str) -> pd.DataFrame:
    ds = xr.open_dataset(filename, decode_times=True)
    df = ds.to_dataframe().reset_index()
    return df

# -------- Load NetCDF data -------- #
def load_nc_dataset(filename) -> WaterFrame:
    WaterFrame.from_netcdf(filename)


def extract_netcdf_metadata(wf):
    """
    Extracts data from a waterframe into .full.json data
    """
    metadata = {
        "global": wf.metadata,
        "variables": wf.vocabulary
    }
    for key in list(metadata["global"].keys()):
        if key.startswith("$"):
            del metadata["global"][key]  # remove special fields

    return metadata


def get_netcdf_metadata(filename):
    """
    Returns the metadata from a NetCDF file
    :param: filename
    :returns: dict with the metadata { "global": ..., "variables": {"VAR1": {...},"VAR2":{...}}
    """
    wf = load_nc_dataset(filename)
    metadata = {
        "global": wf.metadata,
        "variables": wf.vocabulary
    }
    return metadata