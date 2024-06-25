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

from .metadata_templates import dimension_metadata, quality_control_metadata
from .netcdf import wf_to_multidim_nc, read_nc
from .utils import drop_duplicates, merge_dicts


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


def get_dimensions(wf):
    """
    returns a list of QC variables within a waterframe
    """
    return [col for col in wf.data.columns if col.upper() in dimensions]


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


def harmonize_dataframe(df, fill_value=fill_value):
    """
    Takes a dataframe and harmonizes all variable names. All vars are converter to upper case except for lat, lon
    and depth.All QC and STD vars are put to uppercase.
    """
    # harmonize time
    for time_key in ["time", "timestamp", "datetime", "date time"]:
        for key in df.columns:
            if key.lower() == time_key:
                df = df.rename(columns={key: "TIME"})

    for var in df.columns:
        skip = False
        for dim in dimensions:  # skip all dimensions and QC related to dimensions
            if var.startswith(dim):
                skip = True
        if not skip:
            df = df.rename(columns={var: var.upper()})

    # make sure that _QC are uppercase
    for var in df.columns:
        if var.lower().endswith("_qc"):
            df = df.rename(columns={var: var[:-3] + "_QC"})

    # make sure that _QC are uppercase
    for var in df.columns:
        if var.lower().endswith("_std"):
            df = df.rename(columns={var: var[:-4] + "_STD"})

    missing_data = qc_flags["missing_value"]
    for col in df.columns:
        # make sure no NaNs are present in the dataframe
        if col.endswith("_QC"):
            if df[col].dtype != int:
                df[col] = df[col].replace(np.nan, missing_data)  # instead of nan put missing value
                df[col] = df[col].astype(int)

        # replace NaN by fill value
        else:
            if df[col].isnull().any():
                df[col] = df[col].replace(np.nan, fill_value)

    return df


# -------- Functions to handle data from CSV files -------- #
def load_csv_data(filename, sep=",") -> (pd.DataFrame, list):
    """
    Loads data from a CSV file and returns a WaterFrame
    """
    if not filename.endswith(".csv"):
        rich.print(f"[yellow]WARNING! extension of file {filename} is not '.csv', trying anyway...")

    header_lines = csv_detect_header(filename, separator=sep)
    df = pd.read_csv(filename, skiprows=header_lines, sep=sep)
    df = df_force_upper_case(df)
    wf = df_to_wf(df)
    wf.metadata["$datafile"] = filename  # Add the filename as a special param
    return wf


def df_to_wf(df: pd.DataFrame) -> WaterFrame:
    """
    Converts a dataframe into a waterframe
    """
    df = harmonize_dataframe(df)
    vocabulary = {c: {} for c in df.columns}
    wf = WaterFrame(df, {}, vocabulary)
    wf.data["TIME"] = pd.to_datetime(wf.data["TIME"])
    return wf




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


def df_force_upper_case(df: pd.DataFrame) -> pd.DataFrame:
    # Force upper case in dimensions
    for key in df.columns:
        if key.upper() in dimensions and key.upper() != key:
            df = df.rename(columns={key: key.upper()})
    return df


def load_data(file: str):
    """
    Opens a CSV or NetCDF data and returns a WaterFrame
    """
    if file.endswith(".csv"):
        wf = load_csv_data(file)
    elif file.endswith(".nc"):
        wf = load_nc_data(file)
    else:
        raise ValueError("Unimplemented file format for data!")

    return wf


def semicolon_to_list(attr: str):
    """
    Converts semi-colon separated list of items into a python list
    """
    if type(attr) == str and ";" in attr:
        return attr.split(";")
    else:
        return attr


# -------- Load NetCDF data -------- #
def load_nc_data(filename, drop_duplicates=False, process_lists=True) -> (WaterFrame, list):
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
    units = wf.vocabulary["TIME"]["units"]
    if "since" not in units:  # netcdf library requires that the units fields has the 'since' keyword
        if "sdn_parameter_urn" in wf.vocabulary["TIME"].keys() and wf.vocabulary["TIME"]["sdn_parameter_urn"] == "SDN:P01::ELTJLD01":
            units = "days since 1950-01-01T00:00:00z"
        else:
            units = "seconds since 1970-01-01T00:00:00z"
    df["TIME"] = nc.num2date(df["TIME"].values, units, only_use_python_datetimes=True, only_use_cftime_datetimes=False)
    df["TIME"] = pd.to_datetime((df["TIME"]), utc=True)
    if drop_duplicates:
        dups = df[df["TIME"].duplicated()]
        if len(dups) > 0:
            rich.print(f"[yellow]WARNING! detected {len(dups)} duplicated times!, deleting")
            df = drop_duplicates(df)

    wf.data = df  # assign data
    wf.metadata["$datafile"] = filename  # Add the filename as a special param

    # make sure that every column in the dataframe has an associated vocabulary
    for varname in wf.data.columns:
        if varname not in wf.vocabulary.keys():
            rich.print(f"[red]ERROR: Variable {varname} not listed in metadata!")
            wf.vocabulary[varname] = {}  # generate empty metadata vocab
    return wf


# -------- Coordinate-related functions -------- #
def add_coordinates(wf: WaterFrame, latitude, longitude, depth):
    """
    Takes a waterframe and adds nominal lat/lon/depth values
    """
    coordinates = {"LATITUDE": latitude, "LONGITUDE": longitude, "DEPTH": depth}
    for name, value in coordinates.items():
        if name not in wf.data.columns:
            wf.data[name] = value
            wf.data[f"{name}_QC"] = qc_flags["nominal_value"]
            wf.vocabulary[name] = dimension_metadata(name)
            wf.vocabulary[f"{name}_QC"] = quality_control_metadata(wf.vocabulary[name]["long_name"])
    return wf


def ensure_coordinates(wf, required=["DEPTH", "LATITUDE", "LONGITUDE"]):
    """
    Make sure that depth, lat and lon variables (and their QC) are properly set
    """
    error = False
    df = wf.data
    for r in required:
        if r not in df.columns:
            error = True
            rich.print(f"[red]Coordinate {r} is missing!")
        if df[r].dtype != np.float64:
            df[r] = df[r].astype(np.float64)

    if error:
        raise ValueError("Coordinates not properly set")


def update_waterframe_metadata(wf: WaterFrame, meta: dict):
    """
    Merges a full metadata JSON dict into a Waterframe
    """
    wf.metadata = merge_dicts(meta["global"], wf.metadata)
    wf.vocabulary = merge_dicts(meta["variables"], wf.vocabulary)

    keywords = get_variables(wf)
    wf.metadata["keywords"] = keywords
    wf.metadata["keywords_vocabulary"] = "SeaDataNet Parameter Discovery Vocabulary"

    # Updating ancillary variables with QC and STD data
    for qc in get_qc_variables(wf):
        varname = qc.replace("_QC", "")
        varmeta = wf.vocabulary[varname]
        if "ancillary_variables" not in varmeta.keys():
            varmeta["ancillary_variables"] = []
        varmeta["ancillary_variables"].append(qc)

    for std in get_std_variables(wf):
        varname = std.replace("_STD", "")
        varmeta = wf.vocabulary[varname]
        if "ancillary_variables" not in varmeta.keys():
            varmeta["ancillary_variables"] = []
        varmeta["ancillary_variables"].append(std)

    # Update variable coordinates with the dataframe dimensions
    for var in get_variables(wf):
        wf.vocabulary[var]["coordinates"] = dimensions

    # check if all fields are filled, otherwise set a blank string
    __global_attr = ["doi", "platform_code", "wmo_platform_code"]
    for attr in __global_attr:
        if attr not in wf.metadata.keys():
            wf.metadata[attr] = ""

    __variable_fields = ["reference_scale", "comment"]
    for attr in __variable_fields:
        for varname in get_variables(wf):
            if attr not in wf.vocabulary[varname].keys():
                wf.vocabulary[varname][attr] = ""

    return wf


def all_equal(values: list):
    """
    checks if all elements in a list are equal
    :param values: input list
    :returns: True/False
    """
    baseline = values[0]
    equals = True
    for element in values[1:]:
        if element != baseline:
            equals = False
            break
    return equals


def consolidate_metadata(dicts: list) -> dict:
    """
    Consolidates metadata in a list of dicts. All dicts are expected to have the same fields. If all the values are
    equal, keep a single value. If the values are not equal, create a list. However, if it is a sensor_* key, all
    values will be kept.
    """
    keys = [key for key in dicts[0].keys()]  # Get the keys from the first dictionary
    final = {}
    for key in keys:
        values = [d[key] for d in dicts]  # get all the values
        if all_equal(values) and not key.startswith("sensor_"):
            final[key] = values[0]  # get the first element only, all are the same!
        else:
            final[key] = values  # put the full list
    return final


def set_multisensor(wf: WaterFrame):
    """
    Looks through all the variables and checks if data comes from two or more sensors. Sets the multisensor flag
    """
    serial_numbers = []
    for varname, varmeta in wf.vocabulary.items():
        if "sensor_serial_number" not in varmeta.keys():
            continue  # avoid QC and STD vars

        if type(varmeta["sensor_serial_number"]) == str:
            if varmeta["sensor_serial_number"] not in serial_numbers:
                serial_numbers.append(varmeta["sensor_serial_number"])
        elif type(varmeta["sensor_serial_number"]) == list:
            for serial in varmeta["sensor_serial_number"]:
                if serial not in serial_numbers:
                    serial_numbers.append(serial)
    if len(serial_numbers) > 1:
        multi_sensor = True
    elif len(serial_numbers) == 1:
        multi_sensor = False
    else:
        wf.metadata["$multisensor"] = False
        raise LookupError("No sensor serial numbers found!!")
    wf.metadata["$multisensor"] = multi_sensor

    return wf


def export_to_netcdf(wf, filename):
    """
    Stores the waterframe to a NetCDF file
    """
    # If only one sensor remove all sensor_id fields
    set_multisensor(wf)
    if not wf.metadata['$multisensor']:
        if "SENSOR_ID" in wf.data.columns:
            del wf.data["SENSOR_ID"]
        if "SENSOR_ID" in wf.vocabulary.keys():
            del wf.vocabulary["SENSOR_ID"]
        dimensions.remove("SENSOR_ID")

    # Remove internal elements in metadata
    [wf.metadata.pop(key) for key in wf.metadata.copy().keys() if key.startswith("$")]
    wf_to_multidim_nc(wf, filename, dimensions, fill_value=fill_value, time_key="TIME", join_attr=";")


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