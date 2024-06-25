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
from .waterframe import WaterFrame


def wf_to_multidim_nc(wf: WaterFrame, filename: str, dimensions: list, fill_value=fill_value, time_key="TIME",
                      join_attr="; ", fill_value_uint8=fill_value_uint8):
    """
    Creates a multidimensinoal NetCDF-4 file
    :param filename: name of the output file
    :param df: pandas dataframe with the data
    :param metadata: dict containing metadata
    :param multiple_sensors
    """

    # Make sure that time is the last entry in the multiindex
    if time_key in dimensions:
        dimensions.remove(time_key)
        dimensions.append(time_key)

    df = wf.data  # Access the DataFrame within the waterframe
    index_df = df[dimensions].copy()  # create a dataframe with only the variables that will be used as indexes
    multiindex = pd.MultiIndex.from_frame(index_df)  # create a multiindex from the dataframe

    # Arrange other variables into a dict
    data = {col: df[col].values for col in df.columns if col not in dimensions}

    # Create a dataframe with multiindex
    data_df = pd.DataFrame(data, index=multiindex)
    dimensions = tuple(dimensions)

    with nc.Dataset(filename, "w", format="NETCDF4") as ncfile:
        for dimension in dimensions:
            data = index_df[dimension].values
            values = np.unique(data)  # fixed-length dimension
            if dimension == time_key:
                # convert timestamp to float
                index_df[time_key] = pd.to_datetime(index_df[time_key])
                times = index_df[time_key].dt.to_pydatetime()
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

        for varname in data_df.columns:
            values = data_df[varname].to_numpy()  # assign values to the variable
            if varname.endswith("_QC"):
                # Store Quality Control as unsigned bytes
                var = ncfile.createVariable(varname, "u1", dimensions, fill_value=fill_value_uint8, zlib=True)
                var[:] = values.astype(np.int8)
            else:
                var = ncfile.createVariable(varname, 'float', dimensions, fill_value=fill_value, zlib=True)
                var[:] = values

            # Adding metadata
            for key, value in wf.vocabulary[varname].items():
                if type(value) == list:
                    values = [str(v) for v in value]
                    value = join_attr.join(values)
                var.setncattr(key, value)

        # Set global attibutes
        for key, value in wf.metadata.items():
            if type(value) == list:
                values = [str(v) for v in value]
                value = join_attr.join(values)
            ncfile.setncattr(key, value)


def read_nc(path, decode_times=True, time_key="TIME"):
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
            time variable, defaults to "TIME"

    Returns
    -------
        wf: WaterFrame
    """
    # Create WaterFrame

    time_units = ""
    if decode_times:
        # decode_times in xarray.open_dataset will erase the unit field from TIME, so store it before it is removed
        ds = xr.open_dataset(path, decode_times=False)
        if time_key in ds.variables and "units" in ds[time_units].attrs.keys():
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

