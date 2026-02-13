#!/usr/bin/env python3
"""
This file contains JSON-based templates for EMSO metadata

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 19/4/23
"""


def quality_control_metadata(long_name):
    """
    Returns the minimal attributes for a quality control variable
    """
    return {
        "long_name": long_name + " quality control flags",
        "conventions": "OceanSITES QC Flags",
        "flag_values": [0, 1, 2, 3, 4, 7, 8, 9],
        "flag_meanings": ["unknown", "good_data", "probably_good_data", "potentially_correctable_bad_data",
                          "bad_data", "nominal_value", "interpolated_value", "missing_value"]
    }



__dimension_metadata = {
    "time": {
        "long_name": "time of measurements",
        # UNIX time: seconds since 1970
        "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ELTMEP01/",
        "standard_name": "time",
        "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UTBB/",
        "units": "seconds since 1970-01-01 00:00:00",
        "variable_type": "coordinate"
    },
    "depth": {
        "long_name": "depth of measurements",
        "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ADEPZZ01",
        "standard_name": "depth",
        "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/ULAA/",
        "units": "m",
        "variable_type": "coordinate"
    },
    "latitude": {
        "long_name": "latitude of measurements",
        "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ALATZZ01",
        "standard_name": "latitude",
        "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UAAA/",
        "units": "degrees_north",
        "variable_type": "coordinate"
    },
    "longitude": {
        "long_name": "longitude of measurements",
        "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ALONZZ01",
        "standard_name": "longitude",
        "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UAAA/",
        "units": "degrees_east",
        "variable_type": "coordinate"
    },
    "precise_latitude": {
        "long_name": "precise latitude",
        "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ALONZZ01",
        "standard_name": "deployment_latitude",
        "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UAAA/",
        "units": "degrees_north",
        "variable_type": "coordinate"
    },
    "precise_longitude": {
        "long_name": "precise longitude",
        "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ALATZZ01",
        "standard_name": "deployment_longitude",
        "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UAAA/",
        "units": "degrees_east",
        "variable_type": "coordinate"
    },
    "sensor_id": {
        "long_name": "Identifier of the sensor that took the measurement"
    },
    "platform_id": {
        "long_name": "Platform where the sensor was deployed"
    }
}

__dimension_metadata_dtypes = {
    "time": "datetime64[ns]",
    "depth": float,
    "latitude": float,
    "longitude": float,
    "precise_latitude": float,
    "precise_longitude": float,
    "sensor_id": str,
    "platform_id": str
}

# valid names for dimensions, default one is the first in each array
time_valid_names = ["time", "TIME", "timestamp"]
depth_valid_names = ["depth", "DEPTH"]
latitude_valid_names = ["latitude", "LATITUDE", "lat", "LAT"]
longitude_valid_names = ["longitude", "LONGITUDE", "lon", "LON"]
sensor_id_valid_names = ["sensor_id", "SENSOR_ID"]
platform_id_valid_names = ["platform_id", "PLATFORM_ID", "station_id", "STATION_ID"]
precise_latitude_valid_names = ["precise_latitude", "precise_lat", "PRECISE_LATITUDE"]
precise_longitude_valid_names = ["precise_longitude", "precise_lon", "PRECISE_LONGITUDE"]

# List of lists of all possible coordinates
coordinates_array = [time_valid_names, depth_valid_names, latitude_valid_names, longitude_valid_names,
                     sensor_id_valid_names, platform_id_valid_names, precise_latitude_valid_names,
                     precise_longitude_valid_names]

def dimension_metadata(dim):
    for dimension_names in coordinates_array:
        if dim in dimension_names:
            # Dimension metadata has always the default name key, which is the first in the array
            return __dimension_metadata[dimension_names[0]].copy()
    raise LookupError(f"Not a valid dimension '{dim}'.")


def coordinate_default_name(coor):
    for coordinate_names in coordinates_array:
        if coor in coordinate_names:
            # Dimension metadata has always the default name key, which is the first in the array
            return coordinate_names[0]

    raise LookupError(f"Not a valid coordinate '{coor}'")


def is_coordinate(varname):
    for coordinate_names in coordinates_array:
        if varname in coordinate_names:
            # Dimension metadata has always the default name key, which is the first in the array
            return True
    return False

def dimension_metadata_keys():
    return list(__dimension_metadata.keys())

def dimension_metadata_dtype(dim):
    if dim not in __dimension_metadata_dtypes.keys():
        raise LookupError(f"Not a valid dimension '{dim}'. Expected one of the following {list(__dimension_metadata_dtypes.keys())}")
    return __dimension_metadata_dtypes[dim]