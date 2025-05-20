#!/usr/bin/env python3
"""

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 29/4/23
"""
import logging

from .waterframe import WaterFrame
import pandas as pd
from .constants import dimensions, qc_flags, fill_value
import numpy as np
import rich
import netCDF4 as nc
import xarray as xr
from .metadata_templates import dimension_metadata, quality_control_metadata
from .utils import merge_dicts


def get_variables(wf):
    """
    returns a list of QC variables within a waterframe
    """
    vars = []
    dimensions_l = [d.lower() for d in dimensions]
    for c in wf.data.columns:
        if not c.endswith("_QC") and not c.endswith("_STD") and c.lower() not in dimensions and c.lower() not in dimensions_l:
            vars.append(c)
    return vars



def get_qc_variables(wf):
    """
    returns a list of QC variables within a waterframe
    """
    return [col for col in wf.data.columns if col.endswith("_QC")]


def get_std_variables(wf):
    """
    returns a list of standard deviation variables within a waterframe
    """
    return [col for col in wf.data.columns if col.endswith("_STD")]


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


def wf_force_upper_case(wf: WaterFrame) -> WaterFrame:
    # Force upper case in dimensions
    for key in wf.data.columns:
        if key.upper() in dimensions and key.upper() != key:
            wf.data = wf.data.rename(columns={key: key.upper()})
            wf.vocabulary[key.upper()] = wf.vocabulary.pop(key)
    return wf


def load_data(file: str) -> pd.DataFrame:
    """
    Opens a CSV or NetCDF data and returns a WaterFrame
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
def load_nc_data(filename, drop_duplicates=True, process_lists=True) -> (WaterFrame, list):
    """
    Loads NetCDF data into a waterframe
    """
    wf = read_nc(filename, decode_times=False)
    if process_lists:  # Process semicolon separated lists
        for key, value in wf.metadata.items():
            wf.metadata[key] = semicolon_to_list(value)

        for var in wf.vocabulary.keys():
            for key, value in wf.vocabulary[var].items():
                wf.vocabulary[var][key] = semicolon_to_list(value)
    wf.data = wf.data.reset_index()

    if "row" in wf.data.columns:
        # a 'row' column may be introduced by reset index if there previous index was an integer
        del wf.data["row"]
    wf = wf_force_upper_case(wf)
    df = wf.data
    units = wf.vocabulary["time"]["units"]
    if "since" not in units:  # netcdf library requires that the units fields has the 'since' keyword
        if "sdn_parameter_urn" in wf.vocabulary["time"].keys() and wf.vocabulary["time"]["sdn_parameter_urn"] == "SDN:P01::ELTJLD01":
            units = "days since 1950-01-01T00:00:00z"
        else:
            units = "seconds since 1970-01-01T00:00:00z"
    df["time"] = nc.num2date(df["time"].values, units, only_use_python_datetimes=True, only_use_cftime_datetimes=False)
    df["time"] = pd.to_datetime((df["time"]), utc=True)
    if drop_duplicates:
        dups = df[df["time"].duplicated()]
        if len(dups) > 0:
            rich.print(f"[yellow]WARNING! detected {len(dups)} duplicated times!, deleting")
            df = df.drop_duplicates(keep="first")

    wf.data = df  # assign data
    wf.metadata["$datafile"] = filename  # Add the filename as a special param

    # make sure that every column in the dataframe has an associated vocabulary
    for varname in wf.data.columns:
        if varname not in wf.vocabulary.keys():
            rich.print(f"[red]ERROR: Variable {varname} not listed in metadata!")
            wf.vocabulary[varname] = {}  # generate empty metadata vocab
    return wf


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
    wf = load_nc_data(filename, process_lists=False)
    metadata = {
        "global": wf.metadata,
        "variables": wf.vocabulary
    }
    return metadata