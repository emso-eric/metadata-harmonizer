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
import datetime
import logging
from typing import assert_type
import numpy as np
import pandas as pd
import netCDF4 as nc
import xarray as xr
import rich
import warnings

from sympy.parsing.maxima import var_name

from src.emso_metadata_harmonizer.metadata import EmsoMetadata
from src.emso_metadata_harmonizer.metadata.constants import iso_time_format
from src.emso_metadata_harmonizer.metadata.metadata_templates import dimension_metadata, quality_control_metadata
from src.emso_metadata_harmonizer.metadata.utils import LoggerSuperclass, CYN

emso = None


# Make sure that we have all the coordinates
def platform_metadata_to_column(df: pd.DataFrame, variable: str, platforms: list) -> pd.DataFrame:
    if variable not in df.columns:
        df[variable] = platforms[0][variable]
    return df

class WaterFrame(LoggerSuperclass):
    def __init__(self, df: pd.DataFrame, metadata: dict):
        """
        This class is a lightweight re-implementation of WaterFrames, originally from mooda package. It has been
        reimplemented due to lack of maintenance of the original package.

        The metadata dict is
        """
        logger = logging.getLogger("emh")
        LoggerSuperclass.__init__(self, logger, "WF", colour=CYN)
        global emso
        if not emso:
            emso = EmsoMetadata()
        self.emso = emso

        # Metadata should have at least 4 keys: global, sensor, platform and variables
        for var in ["global", "sensors", "platforms", "variables"]:
            assert var in metadata.keys(), f"Key '{var}' missing from metadata"

        if "time" not in df.columns:
            df = df.reset_index()

        assert "index" not in df.columns
        assert type(df) is pd.DataFrame
        assert type(metadata) is dict
        assert "time" in df.columns, "Missing time column in dataframe"
        

        for m in ["global", "variables", "sensors", "platforms"]:
            assert m in metadata.keys(), f"section {m} not in metadata document!"
            assert isinstance(metadata[m], dict), f"section '{m}' should be a dict, got {type(m)} instead!"

        metadata_entries = list(metadata["variables"].keys()) + list(metadata["sensors"].keys()) + list(metadata["platforms"].keys())

        # Possible dimensions
        coordinates = ["time", "depth", "latitude", "longitude", "sensor_id", "platform_id", "precise_latitude", "precise_longitude"]

        for var in df.columns:
            # ensure that every column is a listed in metadata or is variable
            if var.endswith("_QC") or var in coordinates:
                # skip QC and coordinates for now
                continue
            assert var in metadata_entries, f"column {var} not listed in metadata!"

        # Set Constants
        self.flag_values = np.array([0, 1, 2, 3, 4, 7, 8, 9]).astype("u1")
        self.flag_meanings =  ['unknown', 'good_data', 'probably_good_data', 'potentially_correctable_bad_data', 'bad_data', 'nominal_value', 'interpolated_value', 'missing_value']

        # Ensure all dimensions are in lower case
        for col in list(df.columns):
            if col.lower() in coordinates:
                df = df.rename(columns={col: col.lower()})

        self.data = df

        # Split metadata into global metadata and variables
        self.vocabulary = metadata["variables"]
        self.metadata = metadata["global"]
        sensors = metadata["sensors"]
        platforms = metadata["platforms"]

        # Add sensors and platforms!
        for key, value in sensors.items():
            sensors[key]["sensor_id"] = key

        for key, value in platforms.items():
            platforms[key]["platform_id"] = key

        sensors, df = self.process_identifiers(sensors, df, "sensor_id")
        platforms, df = self.process_identifiers(platforms, df, "platform_id")

        # Add sensors and platforms!
        for key, value in sensors.items():
            sensors[key]["sensor_id"] = key

        for key, value in platforms.items():
            platforms[key]["platform_id"] = key

        for var in df.columns:
            # If not defined by the user, use the default coordinate metadata
            if var not in self.vocabulary.keys() and var in coordinates:
                self.debug(f"Using default '{var}' metadata")
                self.vocabulary[var] = dimension_metadata(var)

            # Automatically assign QC metadata
            elif var not in self.vocabulary.keys() and var.endswith("_QC") and var not in self.vocabulary.keys():
                long_name = self.vocabulary[var.split("_QC")[0]]["long_name"]  # get the long name
                self.vocabulary[var] = quality_control_metadata(long_name)

        for variable in ["latitude", "longitude", "depth", "platform_id"]:
            # Convert metadata into columns if not defined
            if variable not in df.columns:
                if len(platforms) == 1:
                    self.info(f"Adding '{variable}' to columns from metadata")
                    df = platform_metadata_to_column(df, variable, list(platforms.values()))
                    self.vocabulary[variable] = dimension_metadata(variable)
                else:
                    self.error(f"'{variable}' must be defined in the CSV files for multi-platform datasets!",
                               exception=ValueError)

        # If we do not have a sensor_id column, we should have exactly one sensor
        if "sensor_id" not in df.columns and len(sensors) > 1:
            raise self.error("sensor_id column is required for datasets with more than one sensor",
                             exception=ValueError)
        elif "sensor_id" not in df.columns and len(sensors) == 1:
            df["sensor_id"] = list(sensors.keys())[0]

        if "sensor_id" not in self.vocabulary.keys():
            self.vocabulary["sensor_id"] = dimension_metadata("sensor_id")

        # If we do not have a platform_id column, we should have exactly one platform
        if len(platforms) == 0:
            raise ValueError("Missing platform metadata")
        elif "platform_id" not in df.columns and  len(platforms) > 1:
            raise ValueError("platform_id column is required for datasets with more than one sensor")
        elif "platform_id" not in df.columns and  len(platforms) == 1:
            # Use the first platform_id
            platform_id = list(platforms.keys())[0]
            df["platform_id"] = platform_id

        # Clear extra vars from vocab
        for key in list(self.vocabulary.keys()):
            if key not in self.data.columns and key not in list(sensors.keys()) + list(platforms.keys()):
                self.info(f"Deleting extra key '{key}' form metadata vocabulary")
                self.vocabulary.pop(key)

        for name, meta in sensors.items():
            meta["variable_type"] = "sensor"
            meta["sensor_id"] = name
            self.vocabulary[name] = meta

        for name, meta in platforms.items():
            meta["variable_type"] = "platform"
            meta["platform_id"] = name
            self.vocabulary[name] = meta

        self.sensors = sensors
        self.platforms = platforms

        self.set_variable_types()

        # Now make sure that all variables have an entry in the metadata (variables, sensors and platforms)
        meta_elements = list(self.vocabulary.keys())
        for col in self.data.columns:
            if col not in meta_elements:
                self.error(f"No metadata for column '{col}'", exception=ValueError)

        self.cf_data_type = ""
        self.cf_alignment()
        self.sort()
        self.__nc_dimensions = {}


    def set_variable_types(self):
        """
        Assigns the variable_type to each variable. Possible values are:
            coordinate: coordinate variable (time, depth, latitude, longitude, sensor_id, platform_id, etc.)
            technical: variable that contains technical information which is not of interest for any scientific use like battery level or error code.
            environmental: Any kind of physical, chemical, and biogeochemical environmental data, compliant with CF
            biological: Any kind of biodiversity / biological variable. Should be compatible with Darwin Core and/or WoRMS
            quality_control: Quality Control flags for another variable
            sensor: variable that hosts sensor metadata
            platform: variable that hosts platform metadata
        """
        for varname in self.data.columns:
            if "variable_type" in self.vocabulary[varname].keys():
                self.debug(f"Variable {varname} already has type='{self.vocabulary[varname]['variable_type']}'")
                continue

            if varname in ["time", "depth", "latitude", "longitude", "sensor_id", "platform_id", "precise_latitude",
                            "precise_longitude"]:
                self.vocabulary[varname]["variable_type"] = "coordinate"

            elif varname.endswith("_QC"):
                self.vocabulary[varname]["variable_type"] = "quality_control"

            elif "sensor_id" in  self.vocabulary[varname].keys():
                self.vocabulary[varname]["variable_type"] = "sensor"

            elif "platform_id" in  self.vocabulary[varname].keys():
                self.vocabulary[varname]["variable_type"] = "platform"
            else:
                # By default, assume environmental variable compatible with climate and forecast
                self.vocabulary[varname]["variable_type"] = "environmental"
            self.debug(f"Assigning {varname} type='{self.vocabulary[varname]['variable_type']}'")

        errors = 0

        for col in self.data.columns:
            if col not in self.vocabulary.keys():
                errors += 1
                self.error(f"Column {col} does not have an entry in metadata vocabulary!")

        if errors > 0:
            raise ValueError("Incomplete metadata")



    def autofill_metadata(self):
        for varname, var in self.vocabulary.items():
            if varname.endswith("_QC") or varname in ["sensor_id", "platform_id"]:
                continue
            if "units" not in var.keys() and var["variable_type"] == "environmental":
                # Get the alternative label from P06
                self.debug(f"Automatically filling units for variable {varname}")
                units = self.emso.vocab_get("P06", var["sdn_uom_uri"], "altLabel")
                self.vocabulary[varname]["units"] = units

        # date_created
        meta = self.metadata
        if "date_created" not in meta.keys():
            self.debug("Derivating date_created")
            self.metadata["date_created"] = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")

        # EDMO codes
        if "institution_edmo_code" in meta.keys() and "institution_edmo_uri" not in meta.keys():
            self.debug("Derivating institution_edmo_code")
            meta["institution_edmo_uri"] = "https://edmo.seadatanet.org/report/" + str(meta["institution_edmo_code"])

        if "institution_edmo_uri" in meta.keys() and "institution_edmo_code" not in meta.keys():
            self.debug("Derivating institution_edmo_code")
            meta["institution_edmo_code"] = meta["institution_edmo_uri"].split("/")[-1]

        # SPDX license
        if "license_uri" not in meta.keys() and "license" in meta.keys():
            meta["license_uri"] = "https://spdx.org/licenses/" + meta["license"]
        if "license" not in meta.keys() and "license_uri" in meta.keys():
            meta["license"] = meta["license"].split("/")[-1]

        # Fill partially defined vocabularies
        for varname, variable in self.vocabulary.items():
            if variable["variable_type"] == "coordinate":
                self.autofill_vocab(variable, "sdn_parameter", "P01")
                self.autofill_vocab(variable, "sdn_uom", "P06")


        for varname, variable in self.vocabulary.items():
            if variable["variable_type"] == "environmental":
                self.autofill_vocab(variable, "sdn_parameter", "P01")
                self.autofill_vocab(variable, "sdn_uom", "P06")

        for varname, variable in self.vocabulary.items():
            if variable["variable_type"] == "sensor":
                self.autofill_vocab(variable, "sdn_instrument", "L22")
                self.autofill_vocab(variable, "sensor_manufacturer", "L35")
                self.autofill_vocab(variable, "sensor_type", "L05")

                # Autofill sensor_SeaVoX_L22_code
                if "sensor_SeaVoX_L22_code" not in variable.keys() and "sdn_instrument_urn" in variable.keys():
                    variable["sensor_SeaVoX_L22_code"] = variable["sdn_instrument_urn"]

        for varname, variable in self.vocabulary.items():
            if variable["variable_type"] == "platform":
                self.autofill_vocab(variable, "platform_type", "L06")

        # Fill coordinate metadata from default table
        df = self.emso.valid_coordinates
        variables = df["coordinate name"].to_list()
        for varname in variables:
            if varname not in self.vocabulary.keys():
                continue
            variable = self.vocabulary[varname]
            if "sdn_parameter_uri" not in variable.keys() and "sdn_parameter_urn" not in variable.keys():
                self.info(f"Using default P01 for {varname}")
                uri = df[df["coordinate name"] == varname]["P01 recommended code"].values[0]
                uri = uri.split("(")[1].split(")")[0]  # remove the Markdown syntax
                variable["sdn_parameter_uri"] = uri
                self.autofill_vocab(variable, "sdn_parameter", "P01")

            if "standard_name" not in variable.keys():
                std_name = df[df["coordinate name"] == varname]["CF standard_name"].values[0]
                if std_name.lower() not in ["n/a", "na", "null"]:
                    variable["standard_name"] = std_name

            self.vocabulary[varname] = variable

        coordinates = [c for c, v in self.vocabulary.items() if v["variable_type"] == "coordinate"]
        coordinates = " ".join(coordinates)

        for varname, variable in self.vocabulary.items():
            if variable["variable_type"] in ["environmental", "biological", "technical"]:
                if  "coordinates" not in variable.keys():
                    variable["coordinates"] = coordinates

        if not self.data.empty:
            self.autofill_coverage()


    def autofill_vocab(self, meta, prefix, vocab_id, exception=False):
        """
        tries to autofill the name, uri and urn for a specific NERC vocabulary.

        Following the specs, any vocabulary should contain the uri, urn and name. For instance

        autofill_vocab(meta, "sdn_units", "P06")
            will force:
            "sdn_units_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UTBB/",
            "sdn_units_urn": "SDN::P06:UTBB"
            "sdn_units_name": "Decibars"
        """
        uri_key = prefix + "_uri"
        urn_key = prefix + "_urn"
        name_key = prefix + "_name"

        if uri_key in meta.keys():
            try:
                uri, urn, preflabel, _ = self.emso.get_vocab_by_uri(vocab_id, meta[uri_key])
            except LookupError:
                return
        elif urn_key in meta.keys():
            try:
                uri, urn, preflabel, _ = self.emso.get_vocab_by_urn(vocab_id, meta[urn_key])
            except LookupError:
                return
        elif exception:
            self.error(f"Could not autofill metadata attribute {prefix} from {vocab_id}", exception=LookupError)
        else:
            return

        if uri_key not in meta.keys():
            meta[uri_key] = uri

        if urn_key not in meta.keys():
            meta[urn_key] = urn

        if name_key not in meta.keys():
            meta[name_key] = preflabel

    def process_identifiers(self, meta, df, key) -> (dict, pd.DataFrame):
        """
        Processes identifiers to align with netcdf conventions (removing special chars)
        """
        for identifier, sensor in meta.copy().items():
            if " " in identifier or "-" in identifier:
                old_identifier = identifier
                identifier = old_identifier.replace(" ", "_").replace("-", "_")
                self.warning(f"identifier '{old_identifier}' contains forbidden chars! converting to '{identifier}'")
                df.loc[df[key] == old_identifier, key] = identifier
                meta[identifier] = meta.pop(old_identifier)
        return meta, df

    def get_cf_type(self) -> str:
        """
        Gets the Climate and Forecast Discrete Sampling Geometry data type based on the data of a single sensor.
        DSG type is usually timeSeries or timeSeriesProfile
        """
        dsgs = []
        for sensor_id in self.data["sensor_id"].unique():
            self.debug(f"Guessing CF type for sensor {sensor_id}")
            df = self.data
            df = df[df["sensor_id"] == sensor_id]
            # timeSeries should have a fixed
            n_lat = len(np.unique(df["latitude"]))
            n_lon = len(np.unique(df["longitude"]))
            n_depth = len(np.unique(df["depth"]))
            if n_depth == n_lon == n_lat == 1:
                # If we only have one lat/lon/depth it is clearly a timeSeries
                self.debug(f"CF type for sensor {sensor_id} is timeSeries depth=latitude=longitude (1)")
                cf_data_type = "timeSeries"
            elif n_lon == n_lat == 1 and n_depth > 1:
                # If we have multiple depths it can be a redeployed sensor. To check it it shou
                cf_data_type = "timeSeries"
                df = df.set_index(["time", "depth"])
                df = df.sort_index()
                df = df.reset_index()
                self.debug(f"Checking rows...")
                for i, time in enumerate(df["time"]):
                    if len(df.loc[df["time"] == time, "depth"]) > 1:
                        # if we have multiple depths at the same time instant it is a profile
                        cf_data_type = "timeSeriesProfile"
                        break
                    elif i > 100:
                        # 100 time points should be enough to determine profile or timeseries
                        break
            elif n_lon > 1 and n_lat > 1 and len(df) > 1:
                # This is a trajectory, not we need to assess if it's a simple trajectory or a trajectoryProfile
                df = df.set_index(["time", "depth"])
                df = df.sort_index()
                df = df.reset_index()
                self.debug(f"Checking rows...")
                # create a dummy column which is an aggregate for time/lat/lon.
                df["position"] = df["latitude"] + df["longitude"] + df["time"].astype(np.int64).astype(np.float128)/1e18

                for i, position in enumerate(df["position"]):
                    if len(df.loc[df["position"] == position, "depth"]) > 1:
                        # if we have multiple depths at the same time instant it is a profile
                        cf_data_type = "trajectoryProfile"
                        break
                    elif i > 100:
                        # 100 time points should be enough to determine profile or timeseries
                        cf_data_type = "trajectory"
                        break

            else:
                raise ValueError(f"Unimplemented CF data type for sensor {sensor_id} with {n_lat} latitudes, {n_lon} longitudes, {n_depth} depths")

            dsgs.append(cf_data_type)

        if all([dsg == "timeSeries" for dsg in dsgs]):
            # If all timeseries
            cf_data_type = "timeSeries"

        elif  all([dsg in ["timeSeries", "timeSeriesProfile"] for dsg in dsgs]):
            cf_data_type = "timeSeriesProfile"
        elif all([dsg == "trajectory" for dsg in dsgs]):
            cf_data_type = "trajectory"
        elif any([dsg == "trajectoryProfile" for dsg in dsgs]):
            cf_data_type = "trajectoryProfile"
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
        self.vocabulary["time"]["monotonic"] = "increasing"
        df = self.data
        if "featureType" not in self.metadata.keys():
            self.info("Guessing CF discrete sampling geometry type...")
            self.cf_data_type = self.get_cf_type()
        else:
            self.cf_data_type = self.metadata["featureType"]

            # ERDDAP changes the first letter to upper case, force lower case
            str_list = list(self.cf_data_type)
            str_list[0] = str_list[0].lower()  # avoid immutable strings error by converting to list and back to string
            self.cf_data_type = "".join(str_list)

            rich.print(f"CF data type already configured: {self.cf_data_type }")

        self.sort()
        self.info(f"CF Data Type: {self.cf_data_type}")

        # Add metadata to Align with ERDDAP CDM data types
        if self.cf_data_type == "timeSeries":
            self.metadata["featureType"] = "timeSeries"
            self.vocabulary["platform_id"]["cf_role"] = "timeseries_id"

        elif self.cf_data_type == "timeSeriesProfile":
            self.metadata["featureType"] = "timeSeriesProfile"
            self.vocabulary["time"]["cf_role"] = "profile_id"
            self.vocabulary["platform_id"]["cf_role"] = "timeseries_id"

        elif self.cf_data_type == "trajectory":
            self.metadata["featureType"] = "trajectory"
            self.vocabulary["platform_id"]["cf_role"] = "trajectory_id"

        elif self.cf_data_type == "trajectoryProfile":
            self.metadata["featureType"] = "trajectoryProfile"
            self.vocabulary["platform_id"]["cf_role"] = "trajectory_id"

        else:
            raise ValueError(f"Unimplemented type {self.cf_data_type}")

        for var in self.vocabulary.keys():
            if var.endswith("_QC"):
                continue
            if "coordinates" in self.vocabulary[var].keys():
                self.vocabulary[var]["coordinates"] = ["time", "latitude", "longitude", "depth", "sensor_id", "platform_id"]

        if "CF-1.8" not in self.metadata["Conventions"]:
            self.metadata["Conventions"] += ["CF-1.8"]

    def sort(self):
        df = self.data
        if self.cf_data_type in ["timeSeries", "timeSeriesProfile", "trajectory", "trajectoryProfile"]:
            df = df.set_index(["time", "depth"])
            df = df.sort_index()
        else:
            raise ValueError(f"Unimplemented CF type '{self.cf_data_type}'")
        df = df.reset_index()
        assert "index" not in df.columns
        self.data = df

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

    def nc_set_global_attributes(self, ncfile):
        # Set global attributes
        for key, value in self.metadata.items():
            if type(value) == list:
                values = [str(v) for v in value]
                value = " ".join(values)
            ncfile.setncattr(key, value)


    def to_netcdf(self, filename):
        """
        Creates a NetCDF file for the time series dataset following CF-1.12 format.
        """
        df = self.data
        # # Arrange variables as coordinates, data variables, qcs
        coordinates = ["time", "depth", "latitude", "longitude", "sensor_id", "platform_id"]
        self.info(f"Creating NetCDF {filename}")
        self.autofill_metadata()

        with nc.Dataset(filename, "w", format="NETCDF4") as ncfile:
            ncfile.createDimension("obs", len(df))  # create row dimension
            self.__nc_dimensions["obs"] = len(df)

            for varname in self.data.columns:
                nc_dtype, nc_fill_value, zlib, values, dimensions = self.nc_process_data_column(df[varname], ncfile)
                var = ncfile.createVariable(varname, nc_dtype, dimensions, zlib=zlib, fill_value=nc_fill_value)
                var[:] = values
                self.populate_var_metadata(varname, var)
                if varname not in coordinates and not varname.endswith("_QC"):
                    if "precise_latitude" not in df.columns:
                        var.setncattr("coordinates", "time depth latitude longitude platform_id sensor_id")
                    else:  # add also precise_latitude and precise_longitude
                        var.setncattr("coordinates", "time depth latitude longitude platform_id sensor_id precise_latitude precise_longitude")
                    ancillary_vars = []
                    for suffix  in ["_QC", "_STD"]:
                        if varname + suffix in df.columns:
                            ancillary_vars.append(varname + suffix)
                    var.setncattr("ancillary_variables", " ".join(ancillary_vars))

                if varname.endswith("_QC"):
                    var.setncattr("flag_values", self.flag_values)
            sensors = {name: s for name, s in self.vocabulary.items() if s["variable_type"] == "sensor"}
            for sensor_id, sensor in sensors.items():
                self.info(f"Creating dummy variable to store '{sensor_id}' metadata")
                var = ncfile.createVariable(sensor_id, "S1", fill_value=" ")
                var.assignValue(" ")
                self.__metadata_from_dict(var, sensor)

            platforms = {name: s for name, s in self.vocabulary.items() if s["variable_type"] == "platform"}
            for platform_id, platform in platforms.items():
                self.info(f"Creating dummy variable to store '{platform_id}' metadata")
                var = ncfile.createVariable(platform_id, "S1", fill_value=" ")
                var.assignValue(" ")
                self.__metadata_from_dict(var, platform)

            self.nc_set_global_attributes(ncfile)

    @staticmethod
    def __nc_compatible_string(series: pd.Series) -> (np.ndarray, int):
        assert_type(series, pd.Series)
        assert pd.api.types.is_string_dtype(series), f"Series '{series.name}' is not a string!"
        if series.empty:
            strlen = 2
        else:
            strlen = max(series.str.len())
        padded_strings = np.array([list(s.ljust(strlen, "\0")) for s in series.values], 'S1')
        return padded_strings, strlen

    def nc_process_data_column(self, series: pd.Series, ncfile: nc.Dataset):
        """
        Takes a pandas series (dataframe column) and detects the NetCDF type, null value, its compressability and more

        :param series: Series
        :param ncfile: nc.Dataset
        :returns:  nc_dtype, nc_fill_value, zlib, values, dimensions
        """
        assert_type(series, pd.Series)
        assert_type(ncfile, nc.Dataset)
        dtype = series.dtype

        # Floats
        if str(series.name).endswith("_QC"):
            series = series.copy()  # copy to avoid SettingWithCopy warning
            series[series.isna()] = 9
            series = series.astype("u1")
            return "u1", 255, True, series.to_numpy().astype("u1"), ("obs",)
        elif pd.api.types.is_float_dtype(dtype):
            return "double", -9999.99, True, series.to_numpy(), ("obs",)
        # QC data
        elif pd.api.types.is_unsigned_integer_dtype(dtype):
            return "u4", 4294967295, True, series.to_numpy(), ("obs",)

        elif pd.api.types.is_integer_dtype(dtype):
            return "i4", -2147483648, True, series.to_numpy(), ("obs",)

        elif pd.api.types.is_string_dtype(dtype):
            # Strings are special in Climate and Forecast, they need to be a matrix of chars with a strlen dimension
            # ["car", "dog"] -> [['c', 'a', 'r'], ['d', 'o', 'g']],
            values, strlen = self.__nc_compatible_string(series)
            dimension_name = str(series.name) + "_strlen"
            if dimension_name not in self.__nc_dimensions.keys():
                ncfile.createDimension(dimension_name, strlen)
                self.__nc_dimensions[dimension_name] = strlen
            return "S1", " ", False, values, ("obs", dimension_name)

        elif pd.api.types.is_datetime64_any_dtype(dtype):
            # Ignore the annoying FutureWarning
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=FutureWarning)
                times = np.array(series.dt.to_pydatetime())
            times = nc.date2num(times, "seconds since 1970-01-01", calendar="standard")
            return "double", -9999.99, True, times, ("obs",)
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

    @staticmethod
    def from_netcdf(filename, decode_times=True) -> "WaterFrame":
        logger = logging.getLogger("emh")
        logger.info(f"Creating WaterFrame from NetCDF file '{filename}'")
        time_units = ""
        if decode_times:
            # decode_times in xarray.open_dataset will erase the unit field from TIME, so store it before it is removed
            ds = xr.open_dataset(filename, decode_times=False)
            if "time" in ds.variables and "units" in ds["time"].attrs.keys():
                time_units = ds["time"].attrs["units"]

            ds.close()

        ds = xr.open_dataset(filename, decode_times=decode_times, decode_cf=True ) # Open file with xarray

        # Save ds into a WaterFrame
        metadata = {"global": dict(ds.attrs), "variables": {}, "sensors": {}, "platforms": {}}
        df = ds.to_dataframe()

        if "time" not in df.columns and "TIME" not in df.columns:
            df = df.reset_index()
            assert "time" in df.columns or "TIME" in df.columns, "Could not find time column in the dataset!"
        for variable in ds.variables:
            metadata["variables"][variable] = dict(ds[variable].attrs)


        if time_units:
            metadata["variables"]["time"]["units"] = time_units

        metadata["sensors"] = collect_sensor_metadata(metadata, df)
        metadata["platforms"] = collect_platform_metadata(metadata, df)
        # Keep only columns with relevant data
        dimensions = ["time", "depth", "latitude", "longitude", "sensor_id", "platform_id"]
        sensor_names = list(metadata["sensors"].keys())
        variables = [v for v in df.columns if v not in dimensions and not v.endswith("_QC") and v not in sensor_names]
        df = df.dropna(subset=variables, how="all")
        wf =  WaterFrame(df, metadata)
        return wf


def __merge_timeseries_waterframes(waterframes: list) -> pd.DataFrame:
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


def __collect_metadata(metadata:dict, df: pd.DataFrame, key) -> dict:
    my_meta = {}
    key_id = key + "_id"
    varnames = metadata["variables"].keys()
    for varname in list(varnames):
        meta = metadata["variables"][varname]
        if key_id in meta.keys():
            # Variables hosting sensor metadata should contain the sensor_id
            my_id = meta[key_id]
            my_meta[my_id] = meta  # add to sensor metadata
            metadata["variables"].pop(varname) # remove from regular metadata
            if varname in df.columns:  # Delete dummy variable with sensor metadata
                del df[varname]
    return my_meta


def collect_sensor_metadata(metadata:dict, df: pd.DataFrame) -> dict:
    return __collect_metadata(metadata, df, "sensor")

def collect_platform_metadata(metadata:dict, df: pd.DataFrame) -> dict:
    return __collect_metadata(metadata, df, "platform")


