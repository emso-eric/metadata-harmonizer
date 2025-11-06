#!/usr/bin/env python3
"""
This file contains JSON-based templates for EMSO metadata

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 19/4/23
"""

import rich
import time


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

def dimension_metadata(dim):

    __dimension_metadata = {
        "time": {
            "long_name": "time of measurements",
            # UNIX time: seconds since 1970
            "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ELTMEP01/",
            "standard_name": "time",
            "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UTBB/"
        },
        "depth": {
            "long_name": "depth of measurements",
            "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ADEPZZ01",
            "standard_name": "depth",
            "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/ULAA/",
            "units": "m"
        },
        "latitude": {
            "long_name": "latitude of measurements",
            "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ALATZZ01",
            "standard_name": "latitude",
            "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UAAA/",
            "units": "degrees_north"
        },
        "longitude": {
            "long_name": "longitude of measurements",
            "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ALONZZ01",
            "standard_name": "longitude",
            "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UAAA/",
            "units": "degrees_east"
        },
        "precise_latitude": {
            "long_name": "precise latitude",
            "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ALONZZ01",
            "standard_name": "deployment_latitude",
            "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UAAA/",
            "units": "degrees_north"
        },
        "precise_longitude": {
            "long_name": "precise longitude",
            "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ALATZZ01",
            "standard_name": "deployment_longitude",
            "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UAAA/",
            "units": "degrees_east"
        },
        "sensor_id": {
            "long_name": "Identifier of the sensor that took the measurement"
        },
        "platform_id": {
            "long_name": "Platform where the sensor was deployed"
        }

    }
    if dim not in __dimension_metadata.keys():
        raise LookupError(f"Not a valid dimension '{dim}'. Expected one of the following {list(__dimension_metadata.keys())}")
    return __dimension_metadata[dim].copy()
