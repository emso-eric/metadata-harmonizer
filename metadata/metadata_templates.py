#!/usr/bin/env python3
"""
This file contains JSON-based templates for EMSO metadata

Conventions:

  '*' Attributes are mandatory, e.g. "*long_name"
  '~' Attributes are optional, if no provided they will be automatically derived from other info
  '$' Attributes are mandatory, but if not present the generator will ask the user to choose it from a list

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 19/4/23
"""

import rich
import time


def variable_metadata():
    """
    Returns all the metadata required in a variable
    """
    return {
        "*long_name": "",
        "*sdn_parameter_uri": "",
        "~sdn_uom_uri": "",
        "~standard_name": "",
    }


def sensor_metadata():
    """
    Returns all the metadata required for a sensor
    """
    return {
        "*sensor_model_uri": "",
        "*sensor_serial_number": "",
        "$sensor_mount": "",
        "$sensor_orientation": ""
    }


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
        "TIME": {
            "long_name": "time of measurements",
            # UNIX time: seconds since 1970
            "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ELTMEP01/",
            "standard_name": "time",
            # Days since 1950
            # "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ELTJLD01/"
            "axis": "T",
            "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UTBB/"
        },
        "DEPTH": {
            "long_name": "depth of measurements",
            "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ADEPZZ01",
            "standard_name": "depth",
            "axis": "Z",
            "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/ULAA/"
        },
        "LATITUDE": {
            "long_name": "latitude of measurements",
            "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ALATZZ01",
            "standard_name": "latitude",
            "axis": "Y",
            "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UAAA/"
        },
        "LONGITUDE": {
            "long_name": "longitude of measurements",
            "sdn_parameter_uri": "https://vocab.nerc.ac.uk/collection/P01/current/ALONZZ01",
            "standard_name": "longitude",
            "axis": "X",
            "sdn_uom_uri": "http://vocab.nerc.ac.uk/collection/P06/current/UAAA/"
        },
        "SENSOR_ID": {
            "long_name": "Identifier of the sensor that took the measurement"
        }
    }
    if dim not in __dimension_metadata.keys():
        raise LookupError(f"Not a valid dimension '{dim}'. Expected one of the following {list(__dimension_metadata.keys())}")
    return __dimension_metadata[dim].copy()


def global_metadata():
    """
    Returns all the metadata required for a sensor
    """
    return {
        "*title": "",
        "*summary": "",
        "~Conventions": "",
        "*institution_edmo_code": "",
        "~update_interval": "",
        "$site_code": "",
        "$emso_facility": "",
        "*source": "",
        "$data_type": "",
        "~format_version": "",
        "~network": "",
        "$data_mode": "",
        "project": "",
        "*principal_investigator": "",
        "*principal_investigator_email": "",
        "~license": ""
    }


def user_selectable_attributes():
    """
    Returns a dict with all the user-selectable metadata attributes
    """
    return {
        "sensor_mount": [
            "mounted_on_fixed_structure",
            "mounted_on_surface_buoy",
            "mounted_on_mooring_line",
            "mounted_on_bottom_lander",
            "mounted_on_moored_profiler",
            "mounted_on_glider",
            "mounted_on_shipborne_fixed",
            "mounted_on_shipborne_profiler",
            "mounted_on_seafloor_structure",
            "mounted_on_benthic_node",
            "mounted_on_benthic_crawler",
            "mounted_on_surface_buoy_tether",
            "mounted_on_seafloor_structure_riser",
            "mounted_on_fixed_subsurface_vertical_profile"
        ],
        "sensor_orientation": ["downward", "upward", "horizontal"],
        "data_type": ["OceanSITES profile data", "OceanSITES time-series data", "OceanSITES trajectory data"],
        "emso_facility": [
            "Azores",
            "Black Sea",
            "Canary Islands",
            "Cretan Sea",
            "Hellenic Arc",
            "Iberian Margin",
            "Western Ligurian Sea",
            "Eastern Ligurian Sea",
            "Molene",
            "OBSEA",
            "SmartBay",
            "South Adriatic Sea",
            "Western Ionian Sea",
            "Western Mediterranean Sea"
        ],
        "site_code": [
            "BB",
            "FF",
            "ALBATROSS-MII (seafloor)",
            "ALBATROSS-MII (mooring)",
            "SJB",
            "DYFAMED",
            "EMSO NICE",
            "W1M3A",
            "OBSEA (seafloor)",
            "OBSEA (buoy)",
            "NEMO-SN1",
            "E2M3A",
            "PYLOS",
            "E1M3A",
            "IbMa-CSV",
            "ESTOC - fixed station",
            "ESTOC - gliders",
            "BOREL2",
            "SeaMoN West",
            "SeaMoN East"
        ],
        "data_mode": [
            "R --> Real-time data", "P --> Provisional data", "D --> Delayed-mode data", "M --> Mixed"
        ]
    }


def choose_interactively(attr_name: str, hint: str, options: list) -> str:
    """
    Asks the user to choose an option from within a list in an interactive manner
    """
    valid_option = False
    n = len(options)
    while not valid_option:
        rich.print(f"[cyan]Select one of the following values for the '{attr_name}' attribute ('{hint}')")
        for i in range(n):
            if i < 9:
                rich.print(" ", end="")
            rich.print(f"{i + 1} - {options[i]}")
        inp = input("Selection: ")
        try:
            selection = int(inp.strip())
        except ValueError:  # invalid user input
            selection = -1

        if type(selection) == int and selection > 0 and selection <= n:
            valid_option = True
        else:
            rich.print("[red]User input not valid! try again...")
            time.sleep(1)
    result = options[selection - 1]
    if "--> " in result:
        result = result.split(" --> ")[0]
    rich.print(f"User selection [purple]'{result}'[/purple]")
    return result