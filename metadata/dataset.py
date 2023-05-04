#!/usr/bin/env python3
"""

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 29/4/23
"""

import mooda as md
import pandas as pd
from metadata.autofill import autofill_waterframe_coverage
from metadata.constants import dimensions, qc_flags, iso_time_format, fill_value
import numpy as np
import rich
import netCDF4 as nc
import cftime

from metadata.metadata_templates import dimension_metadata, quality_control_metadata
from metadata.netcdf import wf_to_multidim_nc
from metadata.utils import drop_duplicates, merge_dicts


def get_variables(wf):
    """
    returns a list of QC variables within a waterframe
    """
    vars = []
    for c in wf.data.columns:
        if not c.endswith("_QC") and not c.endswith("_STD") and c.lower() not in dimensions:
            vars.append(c)
    return vars


def get_dimensions(wf):
    """
    returns a list of QC variables within a waterframe
    """
    return [col for col in wf.data.columns if col in dimensions]


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
                df = df.rename(columns={key: "time"})

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
    df = harmonize_dataframe(df)
    dups = df[df["time"].duplicated()]
    if len(dups) > 0:
        rich.print(f"[yellow]WARNING! detected {len(dups)} duplicated times!, deleting")
        df = drop_duplicates(df)
    wf = md.WaterFrame()
    wf.data = df  # assign data
    wf.metadata = {"$datafile": filename}  # Add the filename as a special param
    wf.vocabulary = {c: {} for c in df.columns}

    wf.data["time"] = pd.to_datetime(wf.data["time"])

    return wf


def csv_detect_header(filename, separator=","):
    """
    Opens a CSV, reads the last 3 lines and extracts the number of fields. Then it goes back to the beginning and
    detects the first line which is not a header
    """
    with open(filename) as f:
        lines = f.readlines()
    nfields = len(lines[-2].split(separator))
    if nfields < 2 or not (nfields == len(lines[-3].split(separator)) == len(lines[-4].split(separator))):
        raise ValueError("Could not determine number of fields")

    # loop until a first a line with nfields is found
    i = 0
    while len(lines[i].split(separator)) != nfields:
        i += 1
    return i


# -------- Load NetCDF data -------- #
def load_nc_data(filename) -> (pd.DataFrame, list):
    """
    Loads NetCDF data into a waterframe
    """
    wf = md.read_nc(filename)
    df = wf.data
    df = df.reset_index()
    df["time"] = cftime.num2pydate(df["time"].values, "seconds since 1970-01-01", calendar="standard")
    df["time"] = pd.to_datetime(df["time"])
    dups = df[df["time"].duplicated()]
    if len(dups) > 0:
        rich.print(f"[yellow]WARNING! detected {len(dups)} duplicated times!, deleting")
        df = drop_duplicates(df)

    wf.data = df  # assign data
    wf.metadata["$datafile"] = filename  # Add the filename as a special param
    return wf


# -------- Coordinate-related functions -------- #
def add_coordinates(wf: md.WaterFrame, latitude, longitude, depth):
    """
    Takes a waterframe and adds nominal lat/lon/depth values
    """
    coordinates = {"latitude": latitude, "longitude": longitude, "depth": depth}
    for name, value in coordinates.items():
        if name not in wf.data.columns:
            rich.print(f"   Adding fixed {name} with value {value}...", end="")
            wf.data[name] = value
            wf.data[f"{name}_QC"] = qc_flags["nominal_value"]
            wf.vocabulary[name] = dimension_metadata(name)
            wf.vocabulary[f"{name}_QC"] = quality_control_metadata(wf.vocabulary[name]["long_name"])
            rich.print("[green]done!")

    return wf


def ensure_coordinates(wf, required=["depth", "latitude", "longitude"]):
    """
    Make sure that depth, lat and lon variables (and their QC) are properly set
    """
    error = False
    df = wf.data
    for r in required:
        if r not in df.columns:
            error = True
            rich.print(f"[red]Coordinate {r} is missing!")
        if df[r].dtype != np.float:
            df[r] = df[r].astype(np.float)

    if error:
        raise ValueError("Coordinates not properly set")


def update_waterframe_metadata(wf: md.WaterFrame, meta: dict):
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
        rich.print(wf.vocabulary[varname])

    return wf


def merge_waterframes(waterframes):
    """
    Combine all WaterFrames into a single waterframe. Both data and metadata are consolidated into a single
    structure
    """
    dataframes = []  # list of dataframes
    global_attr = []  # list of dict containing global attributes
    variables_attr = {}  # dict all the variables metadata
    i = 0
    for wf in waterframes:
        df = wf.data
        # setting time as the index

        df = df.set_index("time")
        df = df.sort_index(ascending=True)
        df["sensor_id"] = wf.metadata["$sensor_id"]

        dataframes.append(df)
        global_attr.append(wf.metadata)
        for varname, varmeta in wf.vocabulary.items():
            if varname not in variables_attr.keys():
                variables_attr[varname] = [varmeta]  # list of dicts with metadata
            else:
                variables_attr[varname].append(varmeta)

    df = pd.concat(dataframes)  # Consolidate data in a single dataframe
    df = df.sort_index(ascending=True)  # sort by date
    df = df.reset_index()  # get back to numerical index

    # Consolidating Global metadata, the position in the array is the priority
    global_meta = {}
    for g in reversed(global_attr):  # loop backwards, last element has lower priority
        global_meta = merge_dicts(g, global_meta)

    variable_meta = {}
    for varname, varmeta in variables_attr.items():
        variable_meta[varname] = consolidate_metadata(varmeta)

    wf = md.WaterFrame()
    wf.data = df
    wf.vocabulary = variable_meta
    wf.metadata = global_meta

    multi_sensor = check_multisensor(wf)
    wf.metadata["$multisensor"] = multi_sensor  # True or false

    wf = autofill_waterframe_coverage(wf)  # update the coordinates max/min in metadata

    # Add versioning info
    now = pd.Timestamp.now(tz="utc").strftime(iso_time_format)
    if len(waterframes) > 1:
        # New waterframe
        wf.metadata["date_created"] = now
        wf.metadata["date_modified"] = now
    else:  # just update the date_modified
        if "date_created" not in wf.metadata.keys():
            wf.metadata["date_created"] = now
        wf.metadata["date_modified"] = wf.metadata["date_created"]
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


def check_multisensor(wf: md.waterframe):
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
        rich.print(f"Multiple sensors found: {serial_numbers}")
        multi_sensor = True
    elif len(serial_numbers) == 1:
        multi_sensor = False
    else:
        raise ValueError("No serial numbers found???")
    return multi_sensor


def export_to_netcdf(wf, filename):
    """
    Stores the waterframe to a NetCDF file
    """
    # Remove internal elements in metadata

    # If only one sensor remove all sensor_id fields
    if not wf.metadata['$multisensor']:
        del wf.data["sensor_id"]
        del wf.vocabulary["sensor_id"]
        dimensions.remove("sensor_id")

    [wf.metadata.pop(key) for key in wf.metadata.copy().keys() if key.startswith("$")]

    rich.print(f"Writing WaterFrame into multidemsncional NetCDF {filename}...", end="")
    wf_to_multidim_nc(wf, filename, dimensions, fill_value=-999, time_key="time")
    rich.print("[green]ok!")

