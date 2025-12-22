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
import os.path
from typing import assert_type
import numpy as np
import pandas as pd
import netCDF4 as nc
import xarray as xr
import rich
import warnings
from src.emso_metadata_harmonizer.metadata.metadata_templates import \
    time_valid_names, depth_valid_names, latitude_valid_names, longitude_valid_names, sensor_id_valid_names, \
    platform_id_valid_names, is_coordinate
from src.emso_metadata_harmonizer.metadata import EmsoMetadata, init_emso_metadata
from src.emso_metadata_harmonizer.metadata.constants import iso_time_format
from src.emso_metadata_harmonizer.metadata.metadata_templates import dimension_metadata, quality_control_metadata, \
    dimension_metadata_keys, dimension_metadata_dtype
from src.emso_metadata_harmonizer.metadata.utils import LoggerSuperclass, CYN
import requests
emso = None


# Make sure that we have all the coordinates
def platform_metadata_to_column(df: pd.DataFrame, variable: str, platforms: list) -> pd.DataFrame:
    if variable not in df.columns:
        try:
            df[variable] = platforms[0][variable]
        except (KeyError, IndexError):
            raise ValueError(f"Cannot extract  field '{variable}' from metadata")
    return df


def set_coordinate_name(df: pd.DataFrame, valid_names, exception=True) -> str:
    for name in valid_names:
        if name in df.columns:
            return name
    if exception:
        raise ValueError(f"Could not find any column for {valid_names[0]}, valid names are: {valid_names}")
    else:
        return valid_names[0]

def get_coordinates_from_dataframe(df: pd.DataFrame) -> (str, str, str, str, str, str):
    """
    Guess coordinates
    :return: time, depth, latitude, longitude, sensor_id, platform_id
    """
    assert isinstance(df, pd.DataFrame)
    _time = set_coordinate_name(df, ["time", "TIME", "timestamp"])
    _depth = set_coordinate_name(df, ["depth", "DEPTH"], exception=False)
    _latitude = set_coordinate_name(df, ["latitude", "LATITUDE", "lat", "LAT"], exception=False)
    _longitude = set_coordinate_name(df, ["longitude", "LONGITUDE", "lon", "LON"], exception=False)
    _sensor_id = set_coordinate_name(df, ["sensor_id", "SENSOR_ID"], exception=False)
    _platform_id = set_coordinate_name(df, ["platform_id", "PLATFORM_ID", "station_id", "STATION_ID"], exception=False)
    return _time, _depth, _latitude, _longitude, _sensor_id, _platform_id


class WaterFrame(LoggerSuperclass):
    def __init__(self, df: pd.DataFrame, metadata: dict, permissive=False):
        """
        This class is a lightweight re-implementation of WaterFrames, originally from mooda package. It has been
        reimplemented due to lack of maintenance of the original package.

        :param df: Pandas dataframe
        :param metadata: metadata dictionary
        :param strict: If True, will raise an error if metadata is missing. If false it will try to continue, use with caution
        """
        self.permissive = permissive
        # Get coordinates from dataframe
        self._time, self._depth, self._latitude, self._longitude, self._sensor_id, self._platform_id = \
            get_coordinates_from_dataframe(df)

        logger = logging.getLogger("emh")
        LoggerSuperclass.__init__(self, logger, "WF", colour=CYN)
        global emso
        if not emso:
            emso = init_emso_metadata()
        self.emso = emso

        # Metadata should have at least 4 keys: global, sensor, platform and variables
        for var in ["global", "sensors", "platforms", "variables"]:
            assert var in metadata.keys(), f"Key '{var}' missing from metadata"

        if self._time not in df.columns:
            df = df.reset_index()

        if "index" in df.columns:
            del df["index"]

        assert type(df) is pd.DataFrame
        assert type(metadata) is dict

        if self._time not in df.columns and "TIME" in df.columns:
            # manually set TIME
            self._time = "TIME"

        assert self._time in df.columns, "Missing time column in dataframe"

        for m in ["global", "variables", "sensors", "platforms"]:
            assert m in metadata.keys(), f"section {m} not in metadata document!"
            assert isinstance(metadata[m], dict), f"section '{m}' should be a dict, got {type(m)} instead!"

        metadata_entries = list(metadata["variables"].keys()) + list(metadata["sensors"].keys()) + list(metadata["platforms"].keys())

        # Possible dimensions
        coordinates = [self._time, self._depth, self._latitude, self._longitude, self._sensor_id, self._platform_id, "precise_latitude", "precise_longitude"]

        for var in df.columns:
            # ensure that every column is a listed in metadata or is variable
            if var.endswith("_QC") or var in coordinates:
                # skip QC and coordinates for now
                continue
            assert var in metadata_entries, f"column {var} not listed in metadata!"

        # Set Constants
        self.flag_values = np.array([0, 1, 2, 3, 4, 7, 8, 9]).astype("u1")
        self.flag_meanings =  ['unknown', 'good_data', 'probably_good_data', 'potentially_correctable_bad_data', 'bad_data', 'nominal_value', 'interpolated_value', 'missing_value']

        self.data = df

        # Split metadata into global metadata and variables
        self.vocabulary = metadata["variables"]
        self.metadata = metadata["global"]
        sensors = metadata["sensors"]
        platforms = metadata["platforms"]

        # Add sensors and platforms!
        for key, value in sensors.items():
            # Add the sensor_id always as lower case
            sensors[key]["sensor_id"] = key

        for key, value in platforms.items():
            platforms[key]["platform_id"] = key

        sensors, df = self.process_identifiers(sensors, df, self._sensor_id)
        platforms, df = self.process_identifiers(platforms, df, self._platform_id)

        for var in df.columns:
            # If not defined by the user, use the default coordinate metadata
            if var not in self.vocabulary.keys() and var in coordinates:
                self.debug(f"Using default '{var}' metadata")
                self.vocabulary[var] = dimension_metadata(var)

            # Automatically assign QC metadata
            elif var not in self.vocabulary.keys() and var.endswith("_QC") and var not in self.vocabulary.keys():
                varname = var.split("_QC")[0]
                if varname in self.vocabulary.keys():
                    long_name = self.vocabulary[varname]["long_name"]  # get the long name
                elif varname.lower()  == "position":
                    long_name = "position"
                else:
                    raise ValueError(f"Cannot relate QC '{var}' to any variable")
                self.vocabulary[var] = quality_control_metadata(long_name)

        for variable in [self._latitude, self._longitude, self._depth, self._platform_id]:
            # Convert metadata into columns if not defined
            if variable not in df.columns:
                if len(platforms) == 1:
                    self.info(f"Adding '{variable}' to columns from metadata")
                    df = platform_metadata_to_column(df, variable, list(platforms.values()))
                    self.vocabulary[variable] = dimension_metadata(variable)
                else:
                    self.error(f"'{variable}' must be defined for multi-platform datasets!",
                               exception=not self.permissive)

        # If we do not have a sensor_id column, we should have exactly one sensor
        if self._sensor_id not in df.columns and len(sensors) > 1:
            raise self.error("sensor_id column is required for datasets with more than one sensor",
                             exception=self.permissive)
        elif self._sensor_id not in df.columns and len(sensors) == 1:
            df[self._sensor_id] = list(sensors.keys())[0]

        if self._sensor_id not in self.vocabulary.keys():
            self.vocabulary[self._sensor_id] = dimension_metadata(self._sensor_id)

        # If we do not have a platform_id column, we should have exactly one platform
        if len(platforms) == 0:
            self.error("Missing platform metadata", exception= not self.permissive)
        elif self._platform_id not in df.columns and  len(platforms) > 1:
            self.error("platform_id column is required for datasets with more than one sensor", exception=self.permissive)
        elif self._platform_id not in df.columns and  len(platforms) == 1:
            # Use the first platform_id
            platform_id = list(platforms.keys())[0]
            df[self._platform_id] = platform_id

        # Clear extra vars from vocab
        for key in list(self.vocabulary.keys()):
            if key not in self.data.columns and key not in list(sensors.keys()) + list(platforms.keys()):
                self.info(f"Deleting extra key '{key}' form metadata vocabulary")
                self.vocabulary.pop(key)

        for name, meta in sensors.items():
            meta["variable_type"] = "sensor"
            meta[self._sensor_id] = name
            self.vocabulary[name] = meta

        for name, meta in platforms.items():
            meta["variable_type"] = "platform"
            meta[self._platform_id] = name
            self.vocabulary[name] = meta

        self.sensors = sensors
        self.platforms = platforms

        self.set_variable_types()

        # Now make sure that all variables have an entry in the metadata (variables, sensors and platforms)
        meta_elements = list(self.vocabulary.keys())
        for col in self.data.columns:
            if col not in meta_elements:

                self.error(f"No metadata for column '{col}'", exception=not self.permissive)

        self.cf_data_type = ""
        self.cf_alignment(strict=not self.permissive)
        self.sort()
        self.__nc_dimensions = {}

    def get_coordinate_names(self):
        """
        Returns the coordinate names (time, depth, lat, lon, sensor_id and platform_id)
        """
        return self._time, self._depth, self._latitude, self._longitude, self._sensor_id, self._platform_id

    def update_coordinate_names(self, source, destination):
        """
        Used only for mapping. If destination is a coordinate, update the key
        """
        if destination == self._time:
            self._time = source
        elif destination == self._depth:
            self._depth = source
        elif destination == self._latitude:
            self._latitude = source
        elif destination == self._longitude:
            self._longitude = source
        elif destination == self._sensor_id:
            self._sensor_id = source
        elif destination == self._platform_id:
            self._platform_id = source

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

            if is_coordinate(varname):
                self.vocabulary[varname]["variable_type"] = "coordinate"

            elif varname.endswith("_QC"):
                self.vocabulary[varname]["variable_type"] = "quality_control"

            elif self._sensor_id in  self.vocabulary[varname].keys():
                self.vocabulary[varname]["variable_type"] = "sensor"

            elif self._platform_id in  self.vocabulary[varname].keys():
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
            if varname.endswith("_QC") or varname in [self._sensor_id, self._platform_id]:
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

        uri_from_name = self.emso.oso.get_uri_from_name
        name_from_uri = self.emso.oso.get_name_from_uri
        # EMSO Regional Facilities
        if "emso_regional_facility_uri" in meta.keys() and "emso_regional_facility_name" not in meta.keys():
            meta["emso_regional_facility_name"] = name_from_uri(meta["emso_regional_facility_uri"], "rfs")

        if "emso_regional_facility_name" in meta.keys() and "emso_regional_facility_uri" not in meta.keys():
            meta["emso_regional_facility_uri"] = uri_from_name(meta["emso_regional_facility_name"], "rfs")

        if "emso_site_uri" in meta.keys() and "emso_site_name" not in meta.keys():
            meta["emso_site_name"] = name_from_uri(meta["emso_site_uri"], "sites")

        if "emso_site_name" in meta.keys() and "emso_site_uri" not in meta.keys():
            meta["emso_site_uri"] = uri_from_name(meta["emso_site_name"], "sites")

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

                meta = self.vocabulary[varname]

                if "emso_platform_name" in meta.keys() and "emso_platform_uri" not in meta.keys():
                    meta["emso_platform_uri"] = uri_from_name(meta["emso_platform_name"], "platforms")

                if "emso_platform_name" in meta.keys() and "emso_platform_uri" not in meta.keys():
                    meta["emso_platform_uri"] = name_from_uri(meta["emso_platform_name"], "platforms")

                self.vocabulary[varname] = meta


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

        for varname, variable in self.vocabulary.items():
            if variable["variable_type"] in ["environmental", "biological", "technical"]:
                variable["coordinates"] = [self._time, self._latitude, self._longitude, self._depth, self._sensor_id, self._platform_id]


        if not self.data.empty:
            self.autofill_coverage()

        # Put as ancillary_variables quality control and related sensors

        for varname, m in self.vocabulary.items():
            # Data Variables will have sensor_id and platform_id in ancillary_variables
            if m["variable_type"] in ["environmental", "biological", "technical"]:
                if "ancillary_variables" not in m.keys():
                    # create a dict where key is varname lower case and value is the true variable name
                    varname_dict = {a.lower(): a for a in self.vocabulary.keys()}

                    expected_qc = f"{varname}_qc".lower() # expected value of the QC variable
                    if expected_qc in varname_dict.keys():
                        m["ancillary_variables"] = varname_dict[expected_qc]
                    else:
                        m["ancillary_variables"] = ""



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
        valid_cf_types = ["timeSeries", "timeSeriesProfile", "trajectory", "trajectoryProfile"]

        def force_valid_cf_type(name):
            for v in valid_cf_types:
                if v.lower() == name.lower():
                    return v
            raise ValueError(f" '{name}' is not a valid CF type")

        if "cf_data_type" in self.metadata.keys():
            # Trust current cf_data_type
            self.cf_data_type = self.metadata["cf_data_type"]
            self.cf_data_type = force_valid_cf_type(self.cf_data_type)
            return self.cf_data_type
        # As an alternative, use cdm_data_type
        elif "cdm_data_type" in self.metadata.keys():
            # Trust current cf_data_type
            self.cf_data_type = self.metadata["cdm_data_type"]
            self.cf_data_type = force_valid_cf_type(self.cf_data_type)
            return self.cf_data_type


        else:
            dsgs = []
            for sensor_id in self.data[self._sensor_id].unique():
                self.debug(f"Guessing CF type for sensor {sensor_id}")
                df = self.data
                df = df[df[self._sensor_id] == sensor_id]
                # timeSeries should have a fixed
                n_lat = len(np.unique(df[self._latitude]))
                n_lon = len(np.unique(df[self._longitude]))
                n_depth = len(np.unique(df[self._depth]))
                if n_depth == n_lon == n_lat == 1:
                    # If we only have one lat/lon/depth it is clearly a timeSeries
                    self.debug(f"CF type for sensor {sensor_id} is timeSeries depth=latitude=longitude (1)")
                    cf_data_type = "timeSeries"
                elif n_lon == n_lat == 1 and n_depth > 1:
                    # If we have multiple depths it can be a redeployed sensor. To check it it shou
                    cf_data_type = "timeSeries"
                    df = df.set_index([self._time, self._depth])
                    df = df.sort_index()
                    df = df.reset_index()
                    self.debug(f"Checking rows...")
                    for i, time in enumerate(df[self._time]):
                        if len(df.loc[df[self._time] == time, self._depth]) > 1:
                            # if we have multiple depths at the same time instant it is a profile
                            cf_data_type = "timeSeriesProfile"
                            break
                        elif i > 100:
                            # 100 time points should be enough to determine profile or timeseries
                            break
                elif n_lon > 1 and n_lat > 1 and len(df) > 1:
                    # This is a trajectory, not we need to assess if it's a simple trajectory or a trajectoryProfile
                    df = df.set_index([self._time, self._depth])
                    df = df.sort_index()
                    df = df.reset_index()
                    self.debug(f"Checking rows...")

                    # create a dummy column which is an aggregate for time/lat/lon.
                    df["position"] = df[self._latitude] + df[self._longitude] + df[self._time].astype(np.int64).astype(np.float128)/1e18

                    for i, position in enumerate(df["position"]):
                        if len(df.loc[df["position"] == position, self._depth]) > 1:
                            # if we have multiple depths at the same time instant it is a profile
                            cf_data_type = "trajectoryProfile"
                            break
                        elif i > 100:
                            # 100 time points should be enough to determine profile or timeseries
                            cf_data_type = "trajectory"
                            break

                    if not cf_data_type:
                        raise ValueError("Unknown cf_data_type")

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

    def cf_alignment(self, strict=False):
        """
        Tries to align the dataset with the Climate and Forecast NetCDF conventions.
        """
        # make sure TIME units is units = "seconds since 1970-01-01 00:00:00" and calendar is gregorian
        self.vocabulary[self._time]["monotonic"] = "increasing"
        if "featureType" not in self.metadata.keys():
            self.info("Guessing CF discrete sampling geometry type...")
            self.cf_data_type = self.get_cf_type()
        else:
            self.cf_data_type = self.metadata["featureType"]

            # ERDDAP changes the first letter to upper case, force lower case
            str_list = list(self.cf_data_type)
            str_list[0] = str_list[0].lower()  # avoid immutable strings error by converting to list and back to string
            self.cf_data_type = "".join(str_list)

            self.info(f"CF data type already configured: {self.cf_data_type }")

        self.sort()
        self.info(f"CF Data Type: {self.cf_data_type}")

        # Add metadata to Align with ERDDAP CDM data types
        if self.cf_data_type == "timeSeries":
            self.metadata["featureType"] = "timeSeries"
            if self._platform_id not in self.vocabulary.keys():
                self.warning(f"No vocabulary entry for {self._platform_id}!")
            else:
                self.vocabulary[self._platform_id]["cf_role"] = "timeseries_id"

        elif self.cf_data_type == "timeSeriesProfile":
            self.metadata["featureType"] = "timeSeriesProfile"
            self.vocabulary[self._time]["cf_role"] = "profile_id"
            self.vocabulary[self._platform_id]["cf_role"] = "timeseries_id"

        elif self.cf_data_type == "trajectory":
            self.metadata["featureType"] = "trajectory"
            self.vocabulary[self._platform_id]["cf_role"] = "trajectory_id"

        elif self.cf_data_type == "trajectoryProfile":
            self.metadata["featureType"] = "trajectoryProfile"
            self.vocabulary[self._platform_id]["cf_role"] = "trajectory_id"

        else:
            self.error(f"Unimplemented type {self.cf_data_type}", exception=not self.permissive)


        if "CF-1.8" not in self.metadata["Conventions"]:
            if isinstance(self.metadata["Conventions"], list):
                self.metadata["Conventions"] += ["CF-1.8"]
            if isinstance(self.metadata["Conventions"], list):
                self.metadata["Conventions"] += " CF-1.8"

    def sort(self):
        if self.data.empty:
            return  # no need to sort an empty dataframe...

        df = self.data
        if self.cf_data_type in ["timeSeries", "timeSeriesProfile", "trajectory", "trajectoryProfile"]:
            df = df.set_index([self._time, self._depth])
            df = df.sort_index()
        else:
            self.error(f"Unimplemented CF type '{self.cf_data_type}'", exception=not self.permissive)
        df = df.reset_index()
        if "index" in df.columns:
            del df["index"]
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

    def force_lower_case_naming(self):
        """
        Forces all dimensions to be lower case. The key (like _time, _depth), the vocabulary and the DataFrame will be changed
        """

        def force_lower_case(ckey, valid_names):
            nkey = valid_names[0]  # by default get the first key
            # Renaming the DataFrame
            self.data = self.data.rename(columns={ckey: nkey})

            def change_key_oneliner(d, old_key, new_key):
                return {new_key if k == old_key else k: v for k, v in d.items()}

            # Rename the metadata
            self.vocabulary = change_key_oneliner(self.vocabulary, ckey, nkey)
            return nkey

        self._time = force_lower_case(self._time, time_valid_names)
        self._depth = force_lower_case(self._depth, depth_valid_names)
        self._latitude = force_lower_case(self._latitude, latitude_valid_names)
        self._longitude = force_lower_case(self._longitude, longitude_valid_names)
        self._sensor_id = force_lower_case(self._sensor_id, sensor_id_valid_names)
        self._platform_id = force_lower_case(self._platform_id, platform_id_valid_names)


    def to_netcdf(self, filename, meta_only=False, keep_names=False):
        """
        Creates a NetCDF file for the time series dataset following CF-1.12 format.

        :param keep_names: If True, names coordinate names are not modified. If False ERDDAP-like lower-case names are forced
        """

        if not keep_names:
            # Forcing variable names to ERDDAP-like style: lower-case
            self.force_lower_case_naming()

        df = self.data

        # # Arrange variables as coordinates, data variables, qcs
        _time = self._time
        _depth = self._depth
        _latitude = self._latitude
        _longitude = self._longitude
        _sensor_id = self._sensor_id
        _platform_id = self._platform_id

        coordinates = [self._time, self._depth, self._latitude, self._longitude, self._sensor_id, self._platform_id]
        self.info(f"Creating NetCDF {filename}")
        self.autofill_metadata()

        if meta_only:
            # Forcing nominal latitude and nominal longitude
            pass

        with nc.Dataset(filename, "w", format="NETCDF4") as ncfile:
            ncfile.createDimension("obs", len(df))  # create row dimension
            self.__nc_dimensions["obs"] = len(df)

            for varname in self.data.columns:
                self.debug(f"Processing variable '{varname}'")
                if meta_only and varname in [self._latitude, self._longitude]:
                    # In metadata only NetCDF files we will force the latitude and longitude later
                    continue

                nc_dtype, nc_fill_value, zlib, values, dimensions = self.nc_process_data_column(df, varname, ncfile)
                var = ncfile.createVariable(varname, nc_dtype, dimensions, zlib=zlib, fill_value=nc_fill_value)
                var[:] = values
                self.populate_var_metadata(varname, var)

                if varname.endswith("_QC"):
                    var.setncattr("flag_values", self.flag_values)

            if meta_only:
                assert len(self.platforms) == 1, "Metadata Only NetCDF files only supported for files with one platform"
                # access platform lat and long
                latitude = self.platforms[list(self.platforms.keys())[0]]["latitude"]
                longitude = self.platforms[list(self.platforms.keys())[0]]["longitude"]

                self.warning("Forcing latitude and longitude!")
                var = ncfile.createVariable("nominal_latitude", "double")
                var[:] = latitude
                var = ncfile.createVariable("nominal_longitude", "double")
                var[:] = longitude

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

    def nc_process_data_column(self, df: pd.DataFrame, varname: str, ncfile: nc.Dataset):
        """
        Takes a pandas series (dataframe column) and detects the NetCDF type, null value, its compressibility and more
        :returns:  nc_dtype, nc_fill_value, zlib, values, dimensions
        """
        assert_type(df, pd.DataFrame)
        assert_type(varname, str)
        assert_type(ncfile, nc.Dataset)
        series = df[varname]

        assert_type(series, pd.Series)

        if isinstance(series, pd.DataFrame):
            # This means empty variable
            rich.print(f"[yellow]WARNING: empty variable using float as default")
            if varname.endswith("_QC"):
                return "double", -9999.99, True, series.to_numpy(), ("obs",)
            else:
                return "u1", 255, True, series.to_numpy().astype("u1"), ("obs",)

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
        self.metadata["geospatial_lat_min"] = self.data[self._latitude].min()
        self.metadata["geospatial_lat_max"] = self.data[self._latitude].max()
        self.metadata["geospatial_lon_min"] = self.data[self._longitude].min()
        self.metadata["geospatial_lon_max"] = self.data[self._longitude].min()
        self.metadata["geospatial_vertical_min"] = int(self.data[self._depth].min())
        self.metadata["geospatial_vertical_max"] = int(self.data[self._depth].min())
        self.metadata["time_coverage_start"] = self.data[self._time].min().strftime(iso_time_format)
        self.metadata["time_coverage_end"] = self.data[self._time].max().strftime(iso_time_format)

    @staticmethod
    def from_erddap(url, dataset_id, protocol="tabledap", permissive=True) -> "WaterFrame":

        url = f"{url}/{protocol}/{dataset_id}.nc"
        rich.print(f"[blue]Downloading NetCDF file fom erddap: {url}")
        r = requests.get(url)
        if r.status_code > 300:
            raise ValueError(f"Cannot retrieve WaterFrame from {url}")
        nbytes = 0
        local_file = f"{dataset_id}.nc"
        with open(local_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    nbytes += 1024
                    print(f"Downloaded {nbytes / (1024**2):.02f} MB...", end="\r")
                    f.write(chunk)
        print("")
        wf = WaterFrame.from_netcdf(local_file, permissive=permissive)
        os.remove(local_file)
        rich.print(f"[blue]WaterFrame created from ERDDAP!")
        return wf

    @staticmethod
    def from_netcdf(filename, decode_times=True, mapper:dict = {}, permissive=False) -> "WaterFrame":
        logger = logging.getLogger("emh")
        logger.info(f"Creating WaterFrame from NetCDF file '{filename}'")
        time_units = ""
        if decode_times:
            # decode_times in xarray.open_dataset will erase the unit field from TIME, so store it before it is removed
            ds = xr.open_dataset(filename, decode_times=False)
            for _time in ["time", "TIME"]:
                if _time in ds.variables and "units" in ds[_time].attrs.keys():
                    time_units = ds[_time].attrs["units"]
                    break

            ds.close()

        ds = xr.open_dataset(filename, decode_times=decode_times, decode_cf=True, decode_coords=False ) # Open file with xarray

        # Save ds into a WaterFrame
        metadata = {"global": dict(ds.attrs), "variables": {}, "sensors": {}, "platforms": {}}
        df = ds.to_dataframe()

        # Rename columns if needed
        for old, new in mapper.items():
            if old in df.columns:
                df.rename(columns={old: new})

        df = df.reset_index()
        # Make sure to delete any leftover from reset index row like index row or obs
        for col in ["index", "row", "obs"]:
            if col in df.columns:
                del df[col]

        _time, _depth, _latitude, _longitude, _sensor_id, _platform_id = get_coordinates_from_dataframe(df)

        if _time not in df.columns:
            df = df.reset_index()
            if "time" in df.columns:
                _time = "time"
            elif "TIME" in df.columns:
                _time = "TIME"


        assert _time in df.columns, f"Could not find time column '{_time}' in the dataset!"

        for variable in ds.variables:
            metadata["variables"][variable] = dict(ds[variable].attrs)

            # Change the name if needed according to the mapper
            if variable in mapper.keys():
                new_var = mapper[variable]
                metadata["variables"][new_var] = metadata["variables"].pop(variable)

        if time_units:
            metadata["variables"][_time]["units"] = time_units


        metadata["sensors"] = collect_sensor_metadata(metadata, df)
        metadata["platforms"] = collect_platform_metadata(metadata, df)
        # Keep only columns with relevant data
        dimensions = [_time, _depth, _latitude, _longitude, _sensor_id, _platform_id]
        sensor_names = list(metadata["sensors"].keys())
        variables = [v for v in df.columns if v not in dimensions and not v.endswith("_QC") and v not in sensor_names]
        df = df.dropna(subset=variables, how="all")
        wf =  WaterFrame(df, metadata, permissive=permissive)
        return wf



    def __repr__(self):
        def get_param(key, vocab):
            if key in vocab.keys():
                return vocab[key]
            return ""

        s = "==== WaterFrame ====\n"
        s += "variables:\n"
        for v in self.vocabulary.keys():
            std_name = get_param("standard_name", self.vocabulary[v])
            units = get_param("units", self.vocabulary[v])
            info = [std_name, units]
            info = [a for a in info if a]  # delete empty
            if info:
                info_str = ", ".join(info)
            else:
                info_str = ""

            s += f"    {v} ({info_str})\n"
        s += "==== Data ====\n"
        s += self.data.__repr__()
        return s


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
    # if self._time not in df.columns:
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


    _time = waterframes[0]._time
    _sensor_id = waterframes[0]._sensor_id
    _platform_id = waterframes[0]._platform_id


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
            if s[_sensor_id] not in [sm[_sensor_id] for sm in metadata["sensors"]]:
                metadata["sensors"].append(s)

        for p in wf.platforms:
            if p[_platform_id] not in [sm[_platform_id] for sm in metadata["platforms"]]:
                metadata["platforms"].append(p)

        for key, var in wf.vocabulary.items():
            if key in [_sensor_id, _platform_id]:
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

    return my_meta


def collect_sensor_metadata(metadata:dict, df: pd.DataFrame) -> dict:
    return __collect_metadata(metadata, df, "sensor")

def collect_platform_metadata(metadata:dict, df: pd.DataFrame) -> dict:
    return __collect_metadata(metadata, df, "platform")



def operational_tests(wf: WaterFrame) -> bool:
    """
    Ensures that the current WaterFrame is operationally sound. The following tests are preformed:
        1. All variables have the variable_type attribute with a valid value
        2. Ensure that we have coordinates with the following names: time, depth, latitude, longitude, sensor_id, platform_id
        3. sensor_id and platform_id values are resolvable identifiers of sensors and platforms metadata variables
    """
    errors = []
    warnings = []
    infos = []
    __valid_coordinates = ["time", "depth", "latitude", "longitude", "sensor_id", "platform_id", "precise_latitude", "precise_longitude"]
    __valid_variable_types = ["environmental", "biological", "technical", "coordinate", "quality_control", "sensor", "platform"]

    rich.print("\n")
    rich.print("[cyan]===== Running Operational tests ====")

    for varname, meta in wf.vocabulary.items():
        if "variable_type" not in meta.keys():
            errors.append(f"variable '{varname}' does not have the mandatory variable_type attribute")
        elif  meta["variable_type"] not in __valid_variable_types:
            errors.append(f"variable '{varname}' does not have a valid variable_type attribute: '{meta['variable_type']}'")
        elif meta["variable_type"] == "coordinate" and varname not in __valid_coordinates:
            errors.append(f"not a valid coordinate name: '{varname}'")

    # Check that sensor_id values are resolvable

    if "sensor_id" in wf.data.keys():
        sensor_ids = wf.data["sensor_id"].unique().astype(str)
        for sensor_id in sensor_ids:
            if sensor_id not in wf.sensors.keys():
                errors.append(f"sensor_id not found in sensors metadata: '{sensor_id}'")
    else:
        errors.append("Coordinate 'sensor_id' not found!")

    # Check that sensor_id values are resolvable
    if "platform_id" in wf.data.keys():
        platform_ids = wf.data["platform_id"].unique().astype(str)
        for platform_id in platform_ids:
            if platform_id not in wf.platforms.keys():
                errors.append(f"not a valid platform_id: '{platform_id}'")
    else:
        errors.append("Coordinate 'platform_id' not found!")


    if len(errors) > 0:
        print(wf)


    rich.print(f"ERRORS: {len(errors)}")
    for e in errors:
        rich.print(f"[red]    ERROR: {e}[/red]")

    rich.print(f"WARNINGS: {len(warnings)}")
    for w in warnings:
        rich.print(f"[yellow]{w}")

    rich.print(f"INFO: {len(warnings)}")
    for i in infos:
        rich.print(f"[cyan]{i}")
    print("")

    if len(errors) == 0:
        rich.print(f"✅ the NetCDF file is operationally sound!")
        return True
    else:

        rich.print(f"❌ the NetCDF file is not operationally valid")
        return True
