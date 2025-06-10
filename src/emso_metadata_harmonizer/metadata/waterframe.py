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

from src.emso_metadata_harmonizer.metadata.constants import iso_time_format, null_by_dtype
from src.emso_metadata_harmonizer.metadata.metadata_templates import dimension_metadata, quality_control_metadata
from src.emso_metadata_harmonizer.metadata.utils import LoggerSuperclass, merge_dicts, CYN


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
        assert "index" not in df.columns
        logger = logging.getLogger("emh")
        LoggerSuperclass.__init__(self, logger,"WF", colour=CYN)
        assert type(df) is pd.DataFrame
        assert type(metadata) is dict
        # Metadata should have at least 4 keys: global, sensor, platform and variables
        for var in ["global", "sensors", "platforms", "variables"]:
            assert var in metadata.keys(), f"Key '{var}' missing from metadata"

        if "time" not in df.columns:
            df = df.reset_index()

        assert "time" in df.columns, "Missing time column in dataframe"

        # Possible dimensions
        self.__dimensions = ["time", "depth", "latitude", "longitude", "sensor_id", "platform_id"]

        # Set Constants
        self.flag_values = np.array([0, 1, 2, 3, 4, 7, 8, 9]).astype("u1")
        self.flag_meanings =  ['unknown', 'good_data', 'probably_good_data', 'potentially_correctable_bad_data', 'bad_data', 'nominal_value', 'interpolated_value', 'missing_value']

        # Ensure all dimensions are in lower case
        for col in list(df.columns):
            if col.lower() in self.__dimensions:
                df = df.rename(columns={col: col.lower()})

        # Split metadata into global metadata and variables
        self.metadata = metadata.pop("global")
        self.sensors = metadata.pop("sensors")
        self.platforms = metadata.pop("platforms")

        for sensor in self.sensors:
            old_sensor_id = sensor["sensor_id"]
            new_sensor_id = old_sensor_id.replace(" ", "_").replace("-", "_")
            sensor["sensor_id"] = new_sensor_id
            if "sensor_id" in df.columns and old_sensor_id in df["sensor_id"].unique():
                df.loc[df["sensor_id"] == old_sensor_id, "sensor_id"] = new_sensor_id

        def platform_metadata_to_column(df: pd.DataFrame, variable: str) -> pd.DataFrame:
            if variable not in df.columns:
                df[variable] = self.platforms[0][variable]
            return df

        df = platform_metadata_to_column(df, "latitude")
        df = platform_metadata_to_column(df, "longitude")
        df = platform_metadata_to_column(df, "depth")
        df = platform_metadata_to_column(df, "platform_id")

        # If we do not have a sensor_id column, we should have exactly one sensor
        if "sensor_id" not in df.columns and len(self.sensors) > 1:
            raise ValueError("sensor_id column is required for datasets with more than one sensor")
        elif "sensor_id" not in df.columns and len(self.sensors) == 1:
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

        # Create a sensor_dict to convert from strings to ints

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
            assert col in self.vocabulary.keys(), f"Vocabulary dict does not have an entry for '{col}'"

        self.cf_data_type = ""
        self.cf_alignment()
        self.sort()
        self.sensor_dict = {s["sensor_id"]: s for s in self.sensors}

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

    def get_cf_type(self) -> str:
        """
        Gets the Climate and Forecast Discrete Sampling Geometry data type based on the data of a single sensor.
        DSG type is usually timeSeries or timeSeriesProfile
        """

        dsgs = []
        for sensor_id in self.data["sensor_id"].unique():
            df = self.data
            df = df[df["sensor_id"] == sensor_id]

            # timeSeries should have a fixed
            n_lat = len(np.unique(df["latitude"]))
            n_lon = len(np.unique(df["longitude"]))
            n_depth = len(np.unique(df["depth"]))
            if n_depth == n_lon == n_lat == 1:
                # If we only have one lat/lon/depth it is clearly a timeSeries
                cf_data_type = "timeSeries"
            elif n_lon == n_lat == 1 and n_depth > 1:
                # If we have multiple depths it can be a redeployed sensor. To check it it shou
                cf_data_type = "timeSeries"
                df = df.set_index(["time", "depth"])
                df = df.sort_index()
                df = df.reset_index()

                for i, time in enumerate(df["time"]):
                    if len(df.loc[df["time"] == time, "depth"]) > 1:
                        # if we have multiple depths at the same time instant it is a profile
                        cf_data_type = "timeSeriesProfile"
                        break
                    elif i > 100:
                        # 100 time points should be enough to determine profile or timeseries
                        break
            elif n_lon > 1 and n_lat > 1 and len(df) > 1:
                cf_data_type = "trajectory"
            else:
                raise ValueError(f"Unimplemented CF data type for sensor {sensor_id} with {n_lat} latitudes, {n_lon} longitudes, {n_depth} depths")

            dsgs.append(cf_data_type)

        if all([dsg == "timeSeries" for dsg in dsgs]):
            # If all all timeseries
            cf_data_type = "timeSeries"

        elif  all([dsg in ["timeSeries", "timeSeriesProfile"] for dsg in dsgs]):
            cf_data_type = "timeSeriesProfile"
        elif all([dsg == "trajectory" for dsg in dsgs]):
            cf_data_type = "trajectory"
        else:
            raise ValueError(f"Cannot create a NetCDF file that mixes different Discrete Sampling Geometries: {dsgs}")

        self.info(f"Detected Discrete Sampling Geometry: {cf_data_type}")
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
        self.cf_data_type = self.get_cf_type()
        self.sort()
        self.info(f"CF Data Type: {self.cf_data_type}")

        # Add metadata to Align with ERDDAP CDM data types
        if self.cf_data_type == "timeSeries":
            self.metadata["featureType"] = "timeSeries"

        elif self.cf_data_type == "timeSeriesProfile":
            self.metadata["featureType"] = "timeSeriesProfile"
            self.vocabulary["time"]["cf_role"] = "profile_id"

        elif self.cf_data_type == "trajectory":
            self.metadata["featureType"] = "trajectory"

        for var in self.vocabulary.keys():
            if var.endswith("_QC"):
                continue
            if "coordinates" in self.vocabulary[var].keys():
                self.vocabulary[var]["coordinates"] = ["time", "latitude", "longitude", "depth", "sensor_id"]

        if "CF-1.8" not in self.metadata["Conventions"]:
            self.metadata["Conventions"] += ["CF-1.8"]

    def sort(self):
        df = self.data
        if self.cf_data_type in ["timeSeries", "timeSeriesProfile", "trajectory"]:
            df = df.set_index(["time", "depth"])
            df = df.sort_index()
        else:
            raise ValueError(f"Unimplemented CF type '{self.cf_data_type}'")
        df = df.reset_index()
        assert "index" not in df.columns
        self.data = df

    def to_netcdf(self, filename):
        """
        Writes a Climate and Forecast compliant dataset!
        """
        if self.cf_data_type == "timeSeries":
            self.to_timeseries_netcdf(filename)
        elif self.cf_data_type == "timeSeriesProfile":
            self.to_timeseries_profile_netcdf(filename)
        elif self.cf_data_type == "trajectory":
            self.to_trajectory_netcdf(filename)
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
                value = [str(s) for s in value]
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

    def nc_add_time_dimension(self, df, ncfile, double_fill=-9999.99):
        # Create time dimension
        ncfile.createDimension("time", len(np.unique(df["time"].values)))  # create dimension
        var = ncfile.createVariable("time", "double", ("time",), fill_value=double_fill, zlib=True)
        times = np.array(df["time"].dt.to_pydatetime())
        var[:] = nc.date2num(np.unique(times), "seconds since 1970-01-01", calendar="standard")
        self.populate_var_metadata("time", var)


    def nc_add_depth_dimension(self, df, ncfile, double_fill=-9999.99):
        ncfile.createDimension("depth", len(df["depth"].unique()))  # create dimension
        var = ncfile.createVariable("depth", "double", ("depth",), fill_value=double_fill, zlib=True)
        var[:] = df["depth"].unique()
        self.populate_var_metadata("depth", var)

    def nc_add_fixed_latitude_longitude(self, ncfile, df):
        # Create latitude and longitude scalars
        for dim in ["latitude", "longitude"]:
            if len(df[dim].unique()) != 1:
                raise ValueError("Expected only one lat/lon for NetCDF file!")
            # Create a scalar variable (no dimensions)
            var = ncfile.createVariable(dim, 'f4')  # 'f4' = 32-bit float
            var.assignValue(df[dim].values[0])
            self.populate_var_metadata(dim, var)

    def nc_add_platform_id(self, ncfile, df):
        strlen = len(df["platform_id"].values[0])
        ncfile.createDimension("strlen", strlen)  # create dimension
        var = ncfile.createVariable('platform_id', 'S1', ('strlen',))
        # Convert station_name into an array of chars
        if len(df["platform_id"].unique()) != 1:
            raise ValueError("Expected only one platform_id for NetCDF file!")
        platform_id = str(df["platform_id"].unique()[0])
        var[:] = np.array([c for c in platform_id.ljust(strlen)])
        self.populate_var_metadata("platform_id", var)
        if self.cf_data_type == "timeSeries":
            var.setncattr("cf_role", "timeseries_id")
        elif self.cf_data_type == "trajectory":
            var.setncattr("cf_role", "trajectory_id")

    def nc_add_sensor_id_dimension(self, ncfile, df):

        # Assign numbers to sensors
        sensor_dict = {name: count + 1 for count, name in enumerate([s["sensor_id"] for s in self.sensors])}
        for sensor_name, sensor_id in sensor_dict.items():
            df.loc[df["sensor_id"] == sensor_name, "sensor_id"] = sensor_id

        df["sensor_id"] = df["sensor_id"].astype(np.uint8)

        # Assign the sensor_id as a code
        ncfile.createDimension("sensor_id", len(df["sensor_id"].unique()))  # create dimension
        nc_dtype, nc_fill, zlib = self.nc_data_types(df["sensor_id"].dtype)
        var = ncfile.createVariable('sensor_id', nc_dtype, ('sensor_id',), fill_value=nc_fill, zlib=zlib)

        # values = df.pivot(index="time", columns="depth", values="sensor_id").to_numpy()
        # values = np.nan_to_num(values, nan=u1_fill)
        var[:] = df["sensor_id"].unique()
        var.setncattr("long_name", "sensor which performed the measurement")

        for sensor in self.sensors:
            sensor_name = sensor["sensor_id"]
            sensor_code = sensor_dict[sensor_name]
            self.info(f"Creating variable to store '{sensor_name}' metadata with value {sensor_code}")
            var = ncfile.createVariable(sensor_name, "u1")
            var.assignValue(sensor_code)
            sensor["sensor_name"] = sensor.pop("sensor_id")  # change "sensor_id" to "sensor_name"
            self.__metadata_from_dict(var, sensor)
            var.setncattr("sensor_id", np.uint8(sensor_code))

    def nc_set_global_attributes(self, ncfile):
        # Set global attributes
        for key, value in self.metadata.items():
            if type(value) == list:
                values = [str(v) for v in value]
                value = " ".join(values)
            ncfile.setncattr(key, value)


    def to_timeseries_netcdf(self, filename, double_fill=-9999.99, u1_fill=255):
        """
        Creates a NetCDF file for the time series dataset following CF-1.12 format.
        """
        df = self.data
        #dimensions = ["time", "depth", "latitude", "longitude", "sensor_id", "platform_id"]
        dimensions = ["time", "depth", "latitude", "longitude"]
        print(df)

        df["platform_id"] = [s.replace("-", "_") for s in df["platform_id"].values]
        variables = [str(c) for c in df.columns if c not in dimensions]

        with nc.Dataset(filename, "w", format="NETCDF4") as ncfile:
            self.nc_add_time_dimension(df, ncfile, double_fill=double_fill)
            self.nc_add_depth_dimension(df, ncfile, double_fill=double_fill)
            #self.nc_add_platform_id(ncfile, df)
            self.nc_add_fixed_latitude_longitude(ncfile, df)
            # self.nc_add_sensor_id_dimension(ncfile, df)

            variables_qc = [varname + "_QC" for varname in variables if varname + "_QC" in df.columns]
            all_varnames = variables + variables_qc
            #arrays = self.df_to_3d_array(df, all_varnames)
            arrays = self.df_to_2d_array(df, all_varnames)
            for varname in variables:
                dtype = df[varname].dtype
                nc_dtype, nc_fill_value, zlib = self.nc_data_types(dtype)
                #var = ncfile.createVariable(varname, nc_dtype, ("time", "depth", "sensor_id"), zlib=True)
                var = ncfile.createVariable(varname, nc_dtype, ("time", "depth"), zlib=True)
                var[:] = arrays[varname]
                self.populate_var_metadata(varname, var)
                var.setncattr("coordinates", "time depth latitude longitude platform_id")
                if varname == "platform_id":
                    var.setncattr("cf_role", "timeseries_id")

            self.nc_set_global_attributes(ncfile)



    def to_timeseries_profile_netcdf(self, filename, double_fill=-9999.99, u1_fill=255):
        """
        Creates a NetCDF file for the time series dataset following CF-1.12 format.
        """
        df = self.data
        dimensions = ["time", "depth", "latitude", "longitude", "sensor_id", "platform_id"]
        # dimensions = ["time", "depth", "latitude", "longitude", "platform_id"]

        variables = [str(c) for c in df.columns if c not in dimensions]
        df["platform_id"] = [s.replace("-", "_") for s in df["platform_id"].values]

        with nc.Dataset(filename, "w", format="NETCDF4") as ncfile:
            self.nc_add_time_dimension(df, ncfile, double_fill=double_fill)
            self.nc_add_depth_dimension(df, ncfile, double_fill=double_fill)
            self.nc_add_platform_id(ncfile, df)
            self.nc_add_fixed_latitude_longitude(ncfile, df)
            self.nc_add_sensor_id_dimension(ncfile, df)

            variables_qc = [varname + "_QC" for varname in variables if varname + "_QC" in df.columns]
            all_varnames = variables + variables_qc
            arrays = self.df_to_3d_array(df, all_varnames)
            # arrays = self.df_to_2d_array(df, all_varnames)
            for varname in variables:
                dtype = df[varname].dtype
                nc_dtype, nc_fill_value, zlib = self.nc_data_types(dtype)
                var = ncfile.createVariable(varname, nc_dtype, ("time", "depth", "sensor_id"), zlib=True)
                #var = ncfile.createVariable(varname, nc_dtype, ("time", "depth"), zlib=True)

                var[:] = arrays[varname]
                self.populate_var_metadata(varname, var)
                var.setncattr("coordinates", "time depth latitude longitude platform_id")

            self.nc_set_global_attributes(ncfile)

    def to_trajectory_netcdf(self, filename, double_fill=-9999.99):
        """
        Creates a NetCDF file for the time series dataset following CF-1.12 format.
        """
        df = self.data
        dimensions = ["time", "sensor_id", "platform_id"]
        # dimensions = ["time", "depth", "latitude", "longitude", "platform_id"]

        variables = [str(c) for c in df.columns if c not in dimensions]
        df["platform_id"] = [s.replace("-", "_") for s in df["platform_id"].values]

        with nc.Dataset(filename, "w", format="NETCDF4") as ncfile:
            self.nc_add_time_dimension(df, ncfile, double_fill=double_fill)
            self.nc_add_platform_id(ncfile, df)
            self.nc_add_sensor_id_dimension(ncfile, df)


            variables_qc = [varname + "_QC" for varname in variables if varname + "_QC" in df.columns]
            all_varnames = variables + variables_qc
            arrays = self.df_to_2d_array(df, all_varnames, column="sensor_id")

            # arrays = self.df_to_2d_array(df, all_varnames)
            for varname in variables:
                dtype = df[varname].dtype
                nc_dtype, nc_fill_value, zlib = self.nc_data_types(dtype)
                var = ncfile.createVariable(varname, nc_dtype, ("time", "sensor_id"), zlib=True)
                #var = ncfile.createVariable(varname, nc_dtype, ("time", "depth"), zlib=True)

                var[:] = arrays[varname]
                self.populate_var_metadata(varname, var)
                var.setncattr("coordinates", "time depth latitude longitude platform_id")

            self.nc_set_global_attributes(ncfile)

    def nc_data_types(self, dtype):
        """
        Converts from pandas data type into NetCDF data type and also returns the fill value and the zlib flag (True for
        compressible variables, false for uncompressible variables).
        :param dtype: pandas data type
        :return: tuple (nc_data_type, nc_fill_value, zlib)
        """
        if dtype in [np.float32, np.float64, np.float128, float]:
            return "f4", -9999.99, True
        elif dtype in [int, np.int32, np.int64]:
            return "i4", -9999.99, True
        elif dtype in [np.uint8]:
            return "u1", 255, True
        elif pd.api.types.is_string_dtype(dtype):
            return "S1", "", True
        else:
            raise ValueError(f"Cannot convert dtype '{dtype}' to NetCDF data type!")


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

    def df_to_3d_array(self, df: pd.DataFrame, varnames):
        assert isinstance(varnames, list)
        for v in varnames:
            assert isinstance(v, str)
            assert v in df.columns
        assert isinstance(df, pd.DataFrame)
        time_vals = np.array(sorted(df["time"].unique()))
        depth_vals = np.array(sorted(df["depth"].unique()))
        sensor_vals = np.array(sorted(df["sensor_id"].unique()))  # string dtype

        # Convert the different indexes into dictionaries
        time_index = {t: i for i, t in enumerate(df["time"].unique())}
        depth_index = {d: i for i, d in enumerate(df["depth"].unique())}
        sensor_index = {s: i for i, s in enumerate(df["sensor_id"].unique())}

        dtypes = [df[varname].dtype for varname in varnames] # keep the same dtype
        arrays = {}  # dictionary where key = varname and value = np array
        for varname, dtype in zip(varnames, dtypes):
            null = null_by_dtype(dtype)  # get the null value for each dtype
            arr = np.full((len(time_vals), len(depth_vals), len(sensor_vals)), null, dtype=dtype)
            arrays[varname] = arr

        # Fill arrays from DataFrame rows
        for _, row in df.iterrows():
            # Get the indexes for the current row
            i = time_index[row["time"]]
            j = depth_index[row["depth"]]
            k = sensor_index[row["sensor_id"]]
            for varname, array in arrays.items():
                array[i, j, k] = row[varname] # assign the values to the variable array

        return arrays

    def df_to_2d_array(self, df: pd.DataFrame, varnames, column="depth"):
        assert isinstance(varnames, list)
        for v in varnames:
            assert isinstance(v, str)
            assert v in df.columns
        assert isinstance(df, pd.DataFrame)

        arrays = {}
        for varname in varnames:
          arrays[varname] = df.pivot(index="time", columns=column, values=varname).to_numpy()

        return arrays

    @staticmethod
    def from_netcdf(filename, decode_times=True) -> "WaterFrame":
        time_units = ""
        if decode_times:
            # decode_times in xarray.open_dataset will erase the unit field from TIME, so store it before it is removed
            ds = xr.open_dataset(filename, decode_times=False)
            if "time" in ds.variables and "units" in ds["time"].attrs.keys():
                time_units = ds["time"].attrs["units"]
            ds.close()

        ds = xr.open_dataset(filename, decode_times=decode_times) # Open file with xarray
        # Save ds into a WaterFrame
        metadata = {"global": dict(ds.attrs), "variables": {}, "sensors": [], "platforms": []}

        df = ds.to_dataframe()


        if "time" not in df.columns:
            df = df.reset_index()
            assert "time" in df.columns, "Could not find time column in the dataset!"
        for variable in ds.variables:
            metadata["variables"][variable] = dict(ds[variable].attrs)

        if time_units:
            metadata["variables"]["time"]["units"] = time_units

        metadata["sensors"] = collect_sensor_metadata(metadata, df)
        metadata["platforms"] = collect_platform_metadata(df)

        # Convert sensor_id from number to text for easier manipulation
        if df["sensor_id"].dtype in [int, np.uint8, np.int8, float, np.float32, np.float64]:
            for sensor_code in df["sensor_id"].unique():
                # look for a variable with "sensor_id" = sensor_code
                sensor_code = int(sensor_code)
                for sensor in metadata["sensors"]:
                    if int(sensor["sensor_id"]) == sensor_code:
                        df.loc[df["sensor_id"] == sensor_code, "sensor_id"] = sensor["sensor_name"]
                        break
        # Convert from sensor_id to string with sensor_name
        for sensor in metadata["sensors"]:
            sensor["sensor_id"] = sensor["sensor_name"]

        # Keep only columns with relevant data
        dimensions = ["time", "depth", "latitude", "longitude", "sensor_id", "platform_id"]
        sensor_names = [s["sensor_name"] for s in metadata["sensors"]]
        variables = [v for v in df.columns if v not in dimensions and not v.endswith("_QC") and v not in sensor_names]
        df = df.dropna(subset=variables)

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

def __merge_timeseries_waterframes(waterframes: [WaterFrame, ]) -> pd.DataFrame:
    dataframes = []
    for wf in waterframes:
        assert isinstance(wf, WaterFrame)
        assert wf.cf_data_type in ["timeSeries"]
        wf.sort()
        dataframes.append(wf.data)
    df = pd.concat(dataframes)
    return df


def __merge_timeseries_profile_waterframes(waterframes: [WaterFrame, ])  -> pd.DataFrame:
    dataframes = []
    for wf in waterframes:
        assert isinstance(wf, WaterFrame)
        assert wf.cf_data_type in ["timeSeries", "timeSeriesProfile"]
        wf.sort()
        dataframes.append(wf.data)

    df = pd.concat(dataframes)
    # if "time" not in df.columns:
    #     df = df.reset_index()
    return df



def merge_waterframes(waterframes):
    """
    Merges data and metadata from several WaterFrames
    """
    if len(waterframes) == 1:
        return waterframes[0]

    # Create the same index for all waterframes
    dsg_types = [wf.cf_data_type for wf in waterframes]
    if all([dsg == "timeSeries" for dsg in dsg_types]):
        df = __merge_timeseries_waterframes(waterframes)
    elif all([dsg in ["timeSeries", "timeSeriesProfile"] for dsg in dsg_types]) and any([dsg == "timeSeriesProfile" for dsg in dsg_types ]):
        df = __merge_timeseries_profile_waterframes(waterframes)
    else:
        raise ValueError(f"Could not merge waterframes with the following types! {dsg_types}")    # Avoid empty waterframes
    waterframes = [wf for wf in waterframes if not wf.data.empty]

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


def collect_sensor_metadata(metadata:dict, df: pd.DataFrame) -> list:
    sensors_meta = []
    varnames = metadata["variables"].keys()
    for varname in list(varnames):
        meta = metadata["variables"][varname]
        if "sensor_id" in meta.keys():
            # Variables hosting sensor metadata should contain the sensor_id
            sensors_meta.append(meta)  # add to sensor metadata
            metadata["variables"].pop(varname) # remove from regular metadata
            if varname in df.columns:  # Delete dummy variable with sensor metadata
                del df[varname]

    return sensors_meta


def collect_platform_metadata(df: pd.DataFrame) -> list:
    platform_meta = []
    platforms = df["platform_id"].unique()
    for platform in platforms:
        if isinstance(platform, bytes):
            platform = platform.decode()
        platform_meta.append({"platform_id": platform, "platform_name": platform})

    return platform_meta


