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
import rich
import netCDF4 as nc
from src.emso_metadata_harmonizer.metadata.utils import LoggerSuperclass


class WaterFrame(LoggerSuperclass):
    def __init__(self, data: pd.DataFrame, metadata: dict, vocabulary: dict):
        """
        This class is a lightweight re-implementation of WaterFrames, originally from mooda package. It has been
        reimplemented due to lack of maintenance of the original package.
        """

        logger = logging.getLogger("emh")
        LoggerSuperclass.__init__(self, logger,"WF")
        assert type(data) is pd.DataFrame
        assert type(metadata) is dict
        assert type(vocabulary) is dict

        # Set Constants
        self.flag_values = np.array([0, 1, 2, 3, 4, 7, 8, 9]).astype("u1")
        self.flag_meanings =  ['unknown', 'good_data', 'probably_good_data', 'potentially_correctable_bad_data', 'bad_data', 'nominal_value', 'interpolated_value', 'missing_value']



        self.data = data  # Here, we should have a dataframe
        self.metadata = metadata
        self.vocabulary = vocabulary
        self.cf_data_type = ""

        # Now make sure that all variables have an entry in the vocabulary
        for col in self.data.columns:
            assert col in self.vocabulary.keys(), f"Vocabulary dict does not have an entry for {col}"


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
        df = self.data.set_index("time")

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
        self.data = df.reset_index()

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


        # Force lower case dimensions
        lower_case_variables = ["time", "latitude", "longitude", "depth", "sensor_id"]
        for c in lower_case_variables:
            if c.upper() in self.data.columns:
                self.data.rename(columns={c.upper(): c})
                self.vocabulary[c] = self.vocabulary.pop(c.upper())

        # Force cf_role = timeseries_id in sensor
        self.vocabulary["sensor_id"]["cf_role"] = "timeseries_id"

        # Force quality control metadata
        for var in self.vocabulary.keys():
            if var.endswith("_QC"):
                self.vocabulary[var]["flag_values"] = self.flag_values
                self.vocabulary[var]["flag_meanings"] = self.flag_meanings
            if "coordinates" in self.vocabulary[var].keys():
                self.vocabulary[var]["coordinates"] = ["time", "latitude", "longitude", "depth", "sensor_id"]

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

    def to_timeseries_netcdf(self, filename, double_fill=-9999.99, u1_fill=255):
        """
        Instance variables (i):
            variables that define a feature, within EMSO the sensor identifier is used. Within CF conventions it is
            suggested station, but a mooring can have sensors at multiple depths, so sensor_id is more suited.

        # More info: https://cfconventions.org/Data/cf-conventions/cf-conventions-1.12/cf-conventions.html#discrete-sampling-geometries

        NetCDFs with timeSeries Discrete Geometry. According CF conventions:
        * Form of a data variable containing values defined on a collection of these features: data(i,o)
        * Mandatory space-time coordinates for a collection of these features: x(i) y(i) t(i,o)
            where i -> time series instance (e.g. platforms or sensors)
                  o -> The subscripts o and p distinguish the data elements that compose a single feature. For example in a
            collection of timeSeries features, each time series instance, i, has data values at various times, o. In a
            collection of profile features, the subscript, o, provides the index position along the vertical axis of
            each profile instance. We refer to data values in a feature as its elements, and to the dimensions of o and
            p as element dimensions.
        """
        df = self.data
        print(df)
        input()
        dimensions = ["time", "sensor_id"]
        aux_variables = ["depth", "latitude", "longitude"]
        variables = [str(c) for c in df.columns if c not in dimensions + aux_variables]
        variables = [v for v in variables if not v.endswith("_QC") and not v.endswith("_STD")]

        n_sensors = len(np.unique(df["sensor_id"]))
        self.info(f"Creating NetCDF file '{filename}' with {n_sensors} sensors")
        self.info(f"    dimensions: {', '.join(dimensions)}")
        self.info(f"     variables: {', '.join(variables)}")
        self.info(f" aux variables: {', '.join(aux_variables)}")

        with nc.Dataset(filename, "w", format="NETCDF4") as ncfile:

            # Create TIME dimensions
            ncfile.createDimension("time", len(df["time"]))  # create dimension
            var = ncfile.createVariable("time", "double", ("time",), fill_value=double_fill, zlib=True)
            times = np.array(df["time"].dt.to_pydatetime())
            var[:] = nc.date2num(times, "seconds since 1970-01-01", calendar="standard")
            self.populate_var_metadata("time", var)

            # Create SENSOR_ID dimensions
            max_length = max([len(s) for s in np.unique(df["sensor_id"].values)])
            ncfile.createDimension('strlen', max_length)
            ncfile.createDimension("sensor_id", n_sensors)  # create dimension
            var = ncfile.createVariable("sensor_id", "S1", ("sensor_id","strlen"), zlib=False)
            values = np.unique(df["sensor_id"])
            # Convert string values into an array with two dimensions
            values = np.array([list(name.ljust(max_length)) for name in values], 'S1')
            var[:] = values
            self.populate_var_metadata("sensor_id", var)
            var.setncattr("cf_role", "timeseries_id")

            for varname in variables:
                var = ncfile.createVariable(varname, "double", ("time", "sensor_id",), zlib=False)
                # Extract the shape with a pivot table
                values = df.pivot(index="time", columns="sensor_id", values=varname).to_numpy()
                print(values)
                var[:] = values
                self.populate_var_metadata(varname, var)

                varname_qc = varname + "_QC"
                if varname_qc in df.columns:
                    var_qc = ncfile.createVariable(varname_qc, "u1", ("time", "sensor_id",), zlib=False, fill_value=u1_fill)
                    # Extract the shape with a pivot table
                    values = df.pivot(index="time", columns="sensor_id", values=varname_qc).to_numpy()
                    values = np.nan_to_num(values, nan=u1_fill)

                    var_qc[:] = values
                    # convert flags to unsigned one byte
                    self.vocabulary[varname_qc]["flag_values"] = self.flag_values
                    self.populate_var_metadata(varname_qc, var_qc)

            for varname in aux_variables:
                self.debug(f"Creating aux variable {varname}")
                # create a pivot table with TIME and SENSOR_ID to extract auxiliary variable values
                table = df.pivot(index="time", columns="sensor_id", values=varname)
                values = []
                qc_values = []
                for sensor_id in np.unique(df["sensor_id"].values):
                    # Get the data variable that matches the sensor and drop all nans
                    v = table[sensor_id].dropna(how='any')
                    unique_v = np.unique(v.values)
                    if len(unique_v) != 1: # we should only have one aux variable value per sensor
                        raise ValueError(f"Expected only one {varname} value for sensor {sensor_id}")
                    values.append(unique_v[0])
                    qc_values.append(7)  # force nominal value

                var = ncfile.createVariable(varname, "double", ("sensor_id",), zlib=False)
                var[:] = values  # assign aux_variables values for every sensor
                self.populate_var_metadata(varname, var, ignore=["ancillary_variables"])

            # Set global attributes
            for key, value in self.metadata.items():
                if type(value) == list:
                    values = [str(v) for v in value]
                    value = " ".join(values)
                ncfile.setncattr(key, value)
