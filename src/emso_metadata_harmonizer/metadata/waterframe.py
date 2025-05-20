#!/usr/bin/env python3
"""
Re-implementation of the WaterFrame class. Originally implemented in the mooda package, it is no longer maintained, so
a custom re-implementation is included here.

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 6/6/24
"""
import logging
import numpy as np
import pandas as pd
import netCDF4 as nc
import xarray as xr
import rich

from src.emso_metadata_harmonizer.metadata.constants import iso_time_format
from src.emso_metadata_harmonizer.metadata.metadata_templates import dimension_metadata, quality_control_metadata
from src.emso_metadata_harmonizer.metadata.utils import LoggerSuperclass, merge_dicts


def df_to_numpy_timeseries(df: pd.DataFrame, variable) -> np.ndarray:
    df = df.copy()
    df["time"] = df["time"].dt.strftime(iso_time_format)
    times = np.sort(np.unique(df['time'].values))
    depths = np.sort(df['depth'].unique())
    sensors = np.sort(df['sensor_id'].unique())

    # Build mappings from coordinate values to array indices
    time_index = {v: i for i, v in enumerate(times)}
    depth_index = {v: i for i, v in enumerate(depths)}
    sensor_index = {v: i for i, v in enumerate(sensors)}
    # Initialize with NaNs (or another fill value)
    temp_array = np.full((len(times), len(depths), len(sensors)), np.nan)

    # Fill the array with TEMP values
    for _, row in df.iterrows():
        t = time_index[row['time']]
        d = depth_index[row['depth']]
        s = sensor_index[row['sensor_id']]
        temp_array[t, d, s] = row[variable]
    return temp_array

def df_to_numpy_timeseries_string(df: pd.DataFrame, variable, strlen) -> np.ndarray:
    df = df.copy()
    df["time"] = df["time"].dt.strftime(iso_time_format)
    times = np.sort(np.unique(df['time'].values))
    depths = np.sort(df['depth'].unique())
    df[variable] = np.array([name.ljust(strlen) for name in df[variable].values])

    # Build mappings from coordinate values to array indices
    time_index = {v: i for i, v in enumerate(times)}
    depth_index = {v: i for i, v in enumerate(depths)}
    # Initialize with NaNs (or another fill value)
    temp_array = np.full((len(times), len(depths), strlen), np.nan, dtype=str)

    for _, row in df.iterrows():
        t = time_index[row['time']]
        d = depth_index[row['depth']]
        for i in range(strlen):
            temp_array[t, d, i] = row[variable][i]
    return temp_array

class WaterFrame(LoggerSuperclass):
    def __init__(self, df: pd.DataFrame, metadata: dict):
        """
        This class is a lightweight re-implementation of WaterFrames, originally from mooda package. It has been
        reimplemented due to lack of maintenance of the original package.

        The metadata dict is
        """
        logger = logging.getLogger("emh")
        LoggerSuperclass.__init__(self, logger,"WF")

        assert type(df) is pd.DataFrame
        assert type(metadata) is dict
        # Metadata should have at least 4 keys: global, sensor, platform and variables
        for var in ["global", "sensors", "platforms", "variables"]:
            assert var in metadata.keys(), f"Key '{var}' missing from metadata"

        # Possible dimensions
        self.__dimensions = ["time", "depth", "latitude", "longitude", "sensor_id", "platform_id"]

        # Set Constants
        self.flag_values = np.array([0, 1, 2, 3, 4, 7, 8, 9]).astype("u1")
        self.flag_meanings =  ['unknown', 'good_data', 'probably_good_data', 'potentially_correctable_bad_data', 'bad_data', 'nominal_value', 'interpolated_value', 'missing_value']

        # Ensure all dimensions are in lower case
        for col in list(df.columns):
            if col.lower() in self.__dimensions:
                df = df.rename(columns={col: col.lower()})

        # Make sure sensor names do not have -
        for i, sensor in enumerate(metadata["sensors"]):
            old_sensor_name = sensor["sensor_id"]
            if "-" in old_sensor_name:
                new_sensor_name = old_sensor_name.replace("-", "_")
                metadata["sensors"][i]["sensor_id"] = new_sensor_name
                if "sensor_id" in df.columns:
                    df["sensor_id"].replace(old_sensor_name, new_sensor_name)


        # Split metadata into global metadata and variables
        self.metadata = metadata.pop("global")
        self.sensors = metadata.pop("sensors")
        self.platforms = metadata.pop("platforms")

        # If we do not have a sensor_id column, we should have exactly one sensor
        if len(self.sensors) == 0:
            raise ValueError("Missing sensor metadata")
        elif "sensor_id" not in df.columns and  len(self.sensors) > 1:
            raise ValueError("sensor_id column is required for datasets with more than one sensor")
        elif "sensor_id" in df.columns:
            sensor_ids = np.unique(df["sensor_id"].values)
            metadata_sensor_ids = [s["sensor_id"] for s in self.sensors]
            for sid in sensor_ids:
                if sid not in metadata_sensor_ids:
                    raise ValueError(f"sensor_id {sid} not found in sensor metadata!")
        else:
            self.info("Manually setting sensor_id")
            df["sensor_id"] = self.sensors[0]["sensor_id"]

        # If we do not have a platform_id column, we should have exactly one platform
        if len(self.platforms) == 0:
            raise ValueError("Missing platform metadata")
        elif "platform_id" not in df.columns and  len(self.platforms) > 1:
            raise ValueError("platform_id column is required for datasets with more than one sensor")
        else:
            df["platform_id"] = self.platforms[0]["platform_id"]

        if "depth" not in df.columns:
            df["depth"] = self.depth_from_metadata()

        if "latitude" not in df.columns or "longitude" not in df.columns:
            latitude, longitude = self.coordinates_from_metadata()
            df["latitude"] = latitude
            df["longitude"] = longitude

        # Move sensor and platform metadata into variables


        metadata["variables"]["sensor_id"] = {"long_name": "sensor which performed the measurement"}
        metadata["variables"]["platform_id"] = {"long_name": "platform where the sensor was deployed"}

        self.data = df
        self.vocabulary = metadata["variables"]

        # If dimension metadata is not set, fill it from the template
        for dim in self.__dimensions:
            if dim.upper().endswith("_QC"):
                continue # skip quality control
            if dim not in self.vocabulary.keys():
                self.vocabulary[dim] = dimension_metadata(dim)

        # If Quality Control metadata is not set, fill it from the template
        for var in df.columns:
            if var.endswith("_QC") and var not in self.vocabulary.keys():
                long_name = self.vocabulary[var.split("_QC")[0]]["long_name"]  # get the long name
                self.vocabulary[var] = quality_control_metadata(long_name)

        # Now make sure that all variables have an entry in the vocabulary
        for col in self.data.columns:
            assert col in self.vocabulary.keys(), f"Vocabulary dict does not have an entry for {col}"

        self.cf_data_type = ""
        self.cf_alignment()

    def determine_strlen(self) -> int:
        """
        Returns the maximum string in string variables and in sensor_ids / platform_ids
        This is useful to calculate the lenght of all strings in the NetCDF file (CF does not allow variable length
        strings)
        """
        variables = ["sensor_id", "platform_id"]
        # Max string length of the values of the variables

        strlen = 0
        for var in variables:
            values = np.unique(self.data[var].values)
            var_max_len = max([len(v) for v in values])
            strlen = max(var_max_len, strlen)
        sensors_ids = max([len(s["sensor_id"]) for s in self.sensors])
        platform_ids = max([len(s["platform_id"]) for s in self.platforms])
        return max(strlen, sensors_ids, platform_ids)

    def get_cf_type(self, sensor_id) -> str:
        """
        Gets the Climate and Forecast Discrete Sampling Geometry data type based on the data of a single sensor.
        DSG type is usually timeSeries or timeSeriesProfile
        """
        df = self.data
        df = df[df["sensor_id"] == sensor_id]
        n_lat = len(np.unique(df["latitude"]))
        n_lon = len(np.unique(df["longitude"]))
        n_depth = len(np.unique(df["depth"]))
        if n_depth == n_lon == n_lat == 1:
            cf_data_type = "timeSeries"
        elif n_lon == n_lat == 1 and n_depth > 1:
            cf_data_type = "timeSeriesProfile"
        else:
            raise ValueError(f"Unimplemented CF data type for sensor {sensor_id}")
        return cf_data_type

    def cf_alignment(self):
        """
        Tries to align the dataset with the Climate and Forecast NetCDF conventions.
        """
        # make sure TIME units is units = "seconds since 1970-01-01 00:00:00" and calendar is gregorian
        self.vocabulary["time"]["units"] = "seconds since 1970-01-01 00:00:00"
        self.vocabulary["time"]["calendar"] = "gregorian"
        self.vocabulary["time"]["monotonic"] = "increasing"
        df = self.data


        rows_orig = len(df)
        self.debug("Detecting duplicated rows...")
        # Drop rows that are equal (keep the first one)

        df = df[~df.duplicated(keep="first")]
        row_no_dups = len(df)
        self.debug("Detecting duplicated indexes...")

        # Drop rows with same index but different values
        df = df[~df.index.duplicated(keep=False)]
        row_no_dups_index = len(df)
        self.debug(f"Detected {rows_orig - row_no_dups} identical rows")
        self.debug(f"Detected {row_no_dups - row_no_dups_index} duplicated indexes (different data)")

        # Split dataframe by sensors
        self.debug("Guessing CF discrete sampling geometry type...")
        cf_dsg_types = []
        for sensor_id in np.unique(df["sensor_id"].values):
            dsg = self.get_cf_type(sensor_id)
            self.debug(f"    {sensor_id} has {dsg} CF type")
            cf_dsg_types.append(dsg)

        if len(np.unique(cf_dsg_types)) != 1:
            raise ValueError(f"Cannot create a NetCDF file that mixes different Discrete Sampling Geometries: {cf_dsg_types}")

        self.cf_data_type = cf_dsg_types[0]  # All are the same, so get the first one

        self.info(f"CF Data Type: {self.cf_data_type}")

        # Add metadata to Align with ERDDAP CDM data types
        if self.cf_data_type == "timeSeries":
            self.metadata["featureType"] = "timeSeries"

        for var in self.vocabulary.keys():
            if var.endswith("_QC"):
                continue
            if "coordinates" in self.vocabulary[var].keys():
                self.vocabulary[var]["coordinates"] = ["time", "latitude", "longitude", "depth", "sensor_id"]

        if "CF-1.8" not in self.metadata["Conventions"]:
            self.metadata["Conventions"] += ["CF-1.8"]



    def to_netcdf(self, filename):
        """
        Writes a Climate and Forecast compliant dataset!
        """
        self.cf_alignment()  # Make sure all attributes are aligned with Climate and Forecast
        if self.cf_data_type == "timeSeries":
            self.to_timeseries_netcdf(filename)
        else:
            raise ValueError(f"Unimplemented CF type {self.cf_data_type}")

    def coordinates_from_metadata(self) -> np.array:
        """
        Guess the coordinates from a metadata dict. The coordinates
        """
        try:
            # Get the latitude longitude from the first station
            latitude = self.platforms[0]["latitude"]
            longitude = self.platforms[0]["latitude"]
        except KeyError:
            raise ValueError("Could not determine latitude/longitude from metadata! is it on sensor or platform?")
        return float(latitude), float(longitude)

    def depth_from_metadata(self) -> float:
        """
        Guess the coordinates from a metadata dict. The coordinates
        """
        if "sensor_depth" in self.sensors[0].keys():
            depth = self.sensors[0]["sensor_depth"]
        else:
            try:
                depth = self.platforms[0]["coordinates"]["depth"]
            except KeyError:
                raise ValueError("Could not determine depthfrom metadata! is it on sensor or platform?")
        return float(depth)

    def populate_var_metadata(self, varname, var: nc.Variable, ignore=[]):
        """
        Populates the metadata of a variable
        """
        for key, value in self.vocabulary[varname].items():
            if key in ignore:  # just ignore this field
                continue

            if isinstance(value, list):
                value = " ".join(value)
            var.setncattr(key, value)

    def __metadata_from_dict(self, var: nc.Variable, meta: dict, ignore=[]):
        """
        Populates the metadata of a variable
        """
        for key, value in meta.items():
            if key in ignore:  # just ignore this field
                continue
            if isinstance(value, list):
                value = " ".join(value)
            var.setncattr(key, value)

    def to_timeseries_netcdf(self, filename, double_fill=-9999.99, u1_fill=255):
        """
        Creates a NetCDF file for the time series dataset following CF-1.12 format.
        """
        df = self.data
        dimensions = ["time", "depth", "latitude", "longitude", "sensor_id", "platform_id"]
        variables = [str(c) for c in df.columns if c not in dimensions]
        variables = [v for v in variables if not v.endswith("_QC") and not v.endswith("_STD")]

        n_sensors = len(np.unique(df["sensor_id"]))
        self.info(f"Creating NetCDF file '{filename}' with {n_sensors} sensors")
        self.info(f"    dimensions: {', '.join(dimensions)}")
        self.info(f"     variables: {', '.join(variables)}")

        df["sensor_id"] = [s.replace("-", "_") for s in df["sensor_id"].values]
        df["platform_id"] = [s.replace("-", "_") for s in df["platform_id"].values]

        with nc.Dataset(filename, "w", format="NETCDF4") as ncfile:
            # Create time dimension
            ncfile.createDimension("time", len(np.unique(df["time"].values))) # create dimension
            var = ncfile.createVariable("time", "double", ("time",), fill_value=double_fill, zlib=True)
            times = np.array(df["time"].dt.to_pydatetime())
            var[:] = nc.date2num(np.unique(times), "seconds since 1970-01-01", calendar="standard")
            self.populate_var_metadata("time", var)

            ncfile.createDimension("depth", len(df["depth"].unique()))  # create dimension
            var = ncfile.createVariable("depth", "double", ("depth",), fill_value=double_fill, zlib=True)
            var[:] = df["depth"].unique()
            self.populate_var_metadata("depth", var)

            # Create a dummy dimension to store text
            strlen = self.determine_strlen()
            ncfile.createDimension("strlen", strlen)  # create dimension

            # Create latitude and longitude scalars
            for dim in ["latitude", "longitude"]:
                if len(df[dim].unique()) != 1:
                    raise ValueError("Expected only one lat/lon for NetCDF file!")
                # Create a scalar variable (no dimensions)
                var = ncfile.createVariable(dim, 'f4')  # 'f4' = 32-bit float
                var.assignValue(df[dim].values[0])
                self.populate_var_metadata(dim, var)

            var = ncfile.createVariable('platform_id', 'S1', ('strlen',))
            # Convert station_name into an array of chars
            if len(df["platform_id"].unique()) != 1:
                raise ValueError("Expected only one platform_id for NetCDF file!")
            platform_id = df["platform_id"].unique()[0]
            var[:] = np.array([c for c in platform_id.ljust(strlen)], 'S1')
            self.populate_var_metadata("platform_id", var)
            var.setncattr("cf_role", "timeseries_id")

            # for sensor in self.sensors:
            #     sensor_id = sensor["sensor_id"]
            #     self.info(f"Creating variable to store '{sensor_id}' metadata")
            #     sensor_var = ncfile.createVariable(sensor_id, "S1", ("strlen",))
            #     var[:] = np.array(sensor_id.ljust(strlen))
            #     self.__metadata_from_dict(sensor_var, sensor)

            for varname in variables:
                var = ncfile.createVariable(varname, "double", ("time", "depth"), zlib=False)
                # Extract the shape with a pivot table
                values = df.pivot(index="time", columns="depth", values=varname).to_numpy()
                var[:] = np.array([values])
                self.populate_var_metadata(varname, var)
                var.setncattr("coordinates", "time depth latitude longitude platform_id")

                varname_qc = varname + "_QC"
                if varname_qc in df.columns:
                    var_qc = ncfile.createVariable(varname_qc, "u1", ("time", "depth"), zlib=False, fill_value=u1_fill)
                    # Extract the shape with a pivot table
                    values = df.pivot(index="time", columns="depth", values=varname_qc).to_numpy()
                    values = np.nan_to_num(values, nan=u1_fill)
                    var_qc[:] = values
                    # convert flags to unsigned one byte
                    self.vocabulary[varname_qc]["flag_values"] = self.flag_values
                    self.populate_var_metadata(varname_qc, var_qc)


            # Set global attributes
            for key, value in self.metadata.items():
                if type(value) == list:
                    values = [str(v) for v in value]
                    value = " ".join(values)
                ncfile.setncattr(key, value)

    def autofill_coverage(self):
        """
        Autofills geospatial and time coverage in a WaterFrame
        """
        self.metadata["geospatial_lat_min"] = self.data["latitude"].min()
        self.metadata["geospatial_lat_max"] = self.data["latitude"].max()
        self.metadata["geospatial_lon_min"] = self.data["longitude"].min()
        self.metadata["geospatial_lon_max"] = self.data["longitude"].min()
        self.metadata["geospatial_vertical_min"] = int(self.data["depth"].min())
        self.metadata["geospatial_vertical_max"] = int(self.data["depth"].min())
        self.metadata["time_coverage_start"] = self.data["time"].min().strftime(iso_time_format)
        self.metadata["time_coverage_end"] = self.data["time"].max().strftime(iso_time_format)

    @staticmethod
    def from_netcdf(filename, decode_times=True) -> "WaterFrame":
        time_units = ""
        if decode_times:
            # decode_times in xarray.open_dataset will erase the unit field from TIME, so store it before it is removed
            ds = xr.open_dataset(filename, decode_times=False)
            if "time" in ds.variables and "units" in ds["time"].attrs.keys():
                time_units = ds["time"].attrs["units"]
            ds.close()

        # Open file with xarray
        ds = xr.open_dataset(filename, decode_times=decode_times)

        # Save ds into a WaterFrame
        metadata = {"global": dict(ds.attrs), "variables": {}, "sensors": [], "platforms": []}

        df = ds.to_dataframe()
        if "time" in df.columns:
            df = df.set_index("time")

        rich.print(ds.variables)

        for variable in ds.variables:
            metadata["variables"][variable] = dict(ds[variable].attrs)

        if time_units:
            metadata["variables"]["time"]["units"] = time_units

        rich.print(metadata)
        return WaterFrame(df, metadata)



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


def merge_waterframes(waterframes):
    """
    Merges data and metadata from several WaterFrames
    """
    if len(waterframes) == 1:
        return waterframes[0]

    # Create the same index for all waterframes
    for wf in waterframes:
        if wf.cf_data_type == "timeSeries":
            wf.data = wf.data.set_index("time")
            wf.data = wf.data.sort_index()
        else:
            raise ValueError("Unimplemented data type")

    # Avoid empty waterframes
    waterframes = [wf for wf in waterframes if not wf.data.empty]

    dataframes = [wf.data for wf in waterframes]  # list of dataframes

    metadata = {
        "global": {},
        "variables": {},
        "sensors": [],
        "platforms": []
    }

    for wf in waterframes:
        # First process global metadata
        for key, value in wf.metadata.items():
            if key not in metadata["global"].keys():
                metadata["global"][key] = value

        for s in wf.sensors:
            if s["sensor_id"] not in [sm["sensor_id"] for sm in metadata["sensors"]]:
                metadata["sensors"].append(s)

        for p in wf.platforms:
            if p["platform_id"] not in [sm["platform_id"] for sm in metadata["platforms"]]:
                metadata["platforms"].append(p)

        for key, var in wf.vocabulary.items():
            if key in ["sensor_id", "platform_id"]:
                continue
            elif key not in metadata["variables"].keys():
                metadata["variables"][key] = var
    df = pd.concat(dataframes)  # Consolidate data in a single dataframe
    df = df.sort_index(ascending=True)  # sort by date
    df = df.reset_index()  # get back to numerical index
    wf = WaterFrame(df, metadata)

    wf.autofill_coverage()  # update the coordinates max/min in metadata

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



#
# def merge_waterframes(waterframes) -> WaterFrame:
#     """
#     Combine all WaterFrames into a single waterframe. Both data and metadata are consolidated into a single
#     structure
#     """
#     dataframes = []  # list of dataframes
#     global_attr = []  # list of dict containing global attributes
#     variables_attr = {}  # dict all the variables metadata
#     for wf in waterframes:
#         df = wf.data
#         # setting time as the index
#         df = df.set_index("time")
#         df = df.sort_index(ascending=True)
#         df["sensor_id"] = wf.metadata["$sensor_id"]
#         if not df.empty:
#             dataframes.append(df)
#         global_attr.append(wf.metadata)
#         for varname, varmeta in wf.vocabulary.items():
#             if varname not in variables_attr.keys():
#                 variables_attr[varname] = [varmeta]  # list of dicts with metadata
#             else:
#                 variables_attr[varname].append(varmeta)
#
#     df = pd.concat(dataframes)  # Consolidate data in a single dataframe
#     df = df.sort_index(ascending=True)  # sort by date
#     df = df.reset_index()  # get back to numerical index
#
#     # Consolidating Global metadata, the position in the array is the priority
#     global_meta = {}
#     for g in reversed(global_attr):  # loop backwards, last element has lower priority
#         global_meta = merge_dicts(g, global_meta)
#
#     variable_meta = {}
#     for varname, varmeta in variables_attr.items():
#         variable_meta[varname] = consolidate_metadata(varmeta)
#
#     wf = WaterFrame(df, global_meta, variable_meta)
#     wf = autofill_waterframe_coverage(wf)  # update the coordinates max/min in metadata
#
#     # Add versioning info
#     now = pd.Timestamp.now(tz="utc").strftime(iso_time_format)
#     if len(waterframes) > 1:
#         # New waterframe
#         wf.metadata["date_created"] = now
#         wf.metadata["date_modified"] = now
#     else:  # just update the date_modified
#         if "date_created" not in wf.metadata.keys():
#             wf.metadata["date_created"] = now
#         wf.metadata["date_modified"] = wf.metadata["date_created"]
#     return wf
