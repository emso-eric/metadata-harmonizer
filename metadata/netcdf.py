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
import mooda as md


def wf_to_multidim_nc(wf: md.WaterFrame, filename: str, dimensions: list, fill_value=-999, time_key="TIME",
                      join_attr="; "):
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
            if type(values[0]) == str:  # Some dimension may be a string (e.g. sesnor_id)
                var = ncfile.createVariable(dimension, str, (dimension,), fill_value=fill_value, zlib=True)
            else:
                var = ncfile.createVariable(dimension, 'f8', (dimension,), fill_value=fill_value, zlib=True)

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
                var = ncfile.createVariable(varname, "u1", dimensions, fill_value=fill_value, zlib=True)
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




