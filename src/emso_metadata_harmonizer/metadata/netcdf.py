#!/usr/bin/env python3
"""
Custom file to create NetCDF files


author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 18/4/23
"""
import netCDF4 as nc
import pandas as pd
import numpy as np
from .constants import fill_value, fill_value_uint8
import xarray as xr
import rich
from .waterframe import WaterFrame



def wf_to_multidim_nc(wf: WaterFrame, filename: str, dimensions: list, fill_value=fill_value,
                      join_attr=" ", fill_value_uint8=fill_value_uint8):
    """
    Creates a multidimensinoal NetCDF-4 file
    :param filename: name of the output file
    :param df: pandas dataframe with the data
    :param metadata: dict containing metadata
    :param multiple_sensors
    """

    return wf.to_netcdf(filename)

    dimensions = wf.dimensions

    rich.print(wf.vocabulary["TEMP_QC"]["flag_values"], f"length {len(wf.vocabulary["TEMP_QC"]["flag_values"])}")
    rich.print(wf.vocabulary["TEMP_QC"]["flag_meanings"], f"length {len(wf.vocabulary["TEMP_QC"]["flag_meanings"])}")

    df = wf.data

    with nc.Dataset(filename, "w", format="NETCDF4") as ncfile:
        for dimension in dimensions:
            data = df[dimension].values
            values = np.unique(data)  # fixed-length dimension
            if dimension == "time":
                # convert timestamp to float
                df["time"] = pd.to_datetime(df["time"])
                times = np.array(df["time"].dt.to_pydatetime())
                values = nc.date2num(times, "seconds since 1970-01-01", calendar="standard")

            ncfile.createDimension(dimension, len(values))  # create dimension
            if type(values[0]) == str:  # Some dimension may be a string (e.g. sensor_id)
                # zlib=False because variable-length strings cannot be compressed
                var = ncfile.createVariable(dimension, str, (dimension,), fill_value=fill_value, zlib=False)
            else:
                var = ncfile.createVariable(dimension, 'float', (dimension,), fill_value=fill_value, zlib=True)

            var[:] = values  # assign dimension values

            # add all dimension metadata

            for key, value in wf.vocabulary[dimension].items():
                if type(value) == list:
                    values = [str(v) for v in value]
                    value = join_attr.join(values)
                var.setncattr(key, value)

        ncfile.createDimension("flags", len(values))  # create dimension
        var = ncfile.createVariable("flags", 'u1', ("flags",), fill_value=127, zlib=True)
        print(wf.flag_values)
        var[:] = wf.flag_values

        for varname in df.columns:
            if varname in dimensions:
                continue
            values = df[varname].to_numpy()  # assign values to the variable
            if varname.endswith("_QC"):
                # Store Quality Control as unsigned bytes
                var = ncfile.createVariable(varname, "u1", dimensions, fill_value=fill_value_uint8, zlib=True)
                var[:] = values.astype(np.int8)
            else:
                var = ncfile.createVariable(varname, 'float', dimensions, fill_value=fill_value, zlib=True)
                var[:] = values

            # Adding metadata
            for key, value in wf.vocabulary[varname].items():
                if key == "flag_values":
                    value = "flags"
                elif type(value) == list:
                    values = [str(v) for v in value]
                    value = join_attr.join(values)

                var.setncattr(key, value)

        # Set global attibutes
        for key, value in wf.metadata.items():
            if key == "flag_value":
                value = flags_var
            if type(value) == list:
                values = [str(v) for v in value]
                value = join_attr.join(values)
            ncfile.setncattr(key, value)


def read_nc(path, decode_times=True, time_key="time"):
    """
    Read data form NetCDF file and create a WaterFrame.

    Parameters
    ----------
        path: str
            Path of the NetCDF file.
        decode_times : bool, optional
            If True, decode times encoded in the standard NetCDF datetime format
            into datetime objects. Otherwise, leave them encoded as numbers.
        time_key:
            time variable, defaults to "time"

    Returns
    -------
        wf: WaterFrame
    """
    # Create WaterFrame

    time_units = ""
    if decode_times:
        # decode_times in xarray.open_dataset will erase the unit field from TIME, so store it before it is removed
        ds = xr.open_dataset(path, decode_times=False)
        if time_key in ds.variables and "units" in ds[time_key].attrs.keys():
            time_units = ds[time_key].attrs["units"]
        ds.close()

    # Open file with xarray
    ds = xr.open_dataset(path, decode_times=decode_times)

    # Save ds into a WaterFrame
    metadata = dict(ds.attrs)

    df = ds.to_dataframe()

    if time_key in df.columns:
        df = df.set_index(time_key)

    vocabulary = {}
    for variable in ds.variables:
        vocabulary[variable] = dict(ds[variable].attrs)

    if time_units:
        vocabulary[time_key]["units"] = time_units
    return WaterFrame(df, metadata, vocabulary)


def new_read_nc2(filename, decode_times=False):

    import rich
    with nc.Dataset(filename, 'r') as dataset:
        varnames = dataset.variables.keys()
        dimnames = dataset.dimensions.keys()
        rich.print(f"Got {len(dimnames)} dimensions: {dimnames}")
        data = {}
        shapes = []
        manual_sizes = {}
        for var in varnames:
            values = dataset.variables[var][:]
            data[var] = values
            shapes.append(values.shape)
            a = 1
            for s in values.shape:
                a *= s
            manual_sizes[a] = var

        rich.print(manual_sizes)
        key_max = max(manual_sizes.keys())
        max_shape = data[var].shape

        reshaped_data = {}
        for key, value in data.items():
            shape = data[key].shape
            rich.print(f"{key} shape = {shape}")
            reshaped_data[key] = value.reshape(max_shape)

        df = pd.DataFrame(reshaped_data)
        print(df)
    exit()

