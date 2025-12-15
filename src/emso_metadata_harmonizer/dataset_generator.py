#!/usr/bin/env python3
"""

Generates NetCDF files based on CSV files and input from the user

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 13/4/23
"""
import json
import logging
import rich
import pandas as pd
import yaml

from .metadata.dataset import load_data
from .metadata import EmsoMetadata
from .metadata.utils import assert_type, LoggerSuperclass
from .metadata.waterframe import WaterFrame, merge_waterframes, get_coordinates_from_dataframe

global_elements = (
    # Array with attribute_name, type, mandatory (True, False), additional_checks
    ("title", str, True),
    ("summary", str, False),
    ("institution", str, True),
    ("institution_edmo_code", str, False),
    ("Conventions", str, False),
    ("update_interval", str, True),
    ("emso_site", str, True),
    ("emso_regional_facility", str, False),
    ("source", str, True),
    ("data_type", str, True),
    ("format_version", str, True),
    ("network", str, True),
    ("data_mode", str, True),
    ("project", str, True),
    ("principal_investigator", str, True),
    ("principal_investigator_email", str, True),
    ("license", str, True)
)

platform_elements = (
    ("long_name", str, True),
    ("wmo_number", str, False),
    ("emso_platform", str, False),
    ("platform_type", str, False),
    ("platform_type_uri", str, True),
    ("info_url", str, True),
    ("comment", str, False),
    ("latitude", float, False),
    ("longitude", float, False)
)

sensor_elements = (
    ("long_name", str, True),
    ("sensor_serial_number", str, True),
    ("sensor_mount", str, False),
    ("sensor_orientation", str, False),
    ("sdn_instrument_uri", str, False),
    ("sdn_instrument_urn", str, False),
    ("sdn_instrument_name", str, False),
    ("sensor_manufacturer_uri", str, False),
    ("sensor_manufacturer_urn", str, False),
    ("sensor_manufacturer_name", str, False),
    ("sensor_type_uri", str, False),
    ("sensor_type_urn", str, False),
    ("sensor_type_name", str, False),
    ("sensor_reference", str, False),
)


common_variable_elements = (
    ("long_name", str, True),
    ("variable_type", str, True)
)

environmental_variable_elements = (
    ("long_name", str, True),
    ("sdn_parameter_uri", str, True),
    ("sdn_uom_uri", str, True),
    ("standard_name", str, True)
)

biological_variable_elements = (
    ("long_name", str, True),
    ("dwc_term_uri", str, True)
)

technical_variable_elements = (
    ("long_name", str, True),
    ("comment", str, True),
    ("units", str, False),
)

coordinate_variable_elements= (
    ("sdn_parameter_uri", str, True),
    ("standard_name", str, True),
    ("sdn_uom_uri", str, True)
)

DEBUG_TESTS = False

def debug_metadata_tests(string, end="\n"):
    if DEBUG_TESTS:
        rich.print(string, end=end)

def validate_metadata(metadata: dict, section: str, rules: tuple, errors: list, warnings: list, key=""):
    """
    Validate
    """
    if section == "global":
        # keep only the global attributes
        under_test = {"global": metadata["global"]}
    else:
        under_test = metadata[section]


    if key:
        # Test only the element with matching key
        under_test = {key: metadata[section][key]}

    if not under_test:
        warnings.append(f"{section} is empty!")
        return

    for element_id, data in under_test.items():
        for key, data_type, mandatory in rules:
            debug_metadata_tests(f"[grey42]testing {section}:{element_id}:{key}...", end="")
            if key not in data.keys():
                if mandatory:
                    errors.append(f"{section}:{element_id} Missing mandatory attribute '{key}'")
                    debug_metadata_tests(f"[red]error")
                else:
                    warnings.append(f"{section}:{element_id} Missing optional attribute '{key}'")
                    debug_metadata_tests(f"[yellow]warning")
                continue
            value = data[key]
            if not isinstance(value, data_type):
                errors.append(f"{section}:{element_id}:{key} must be {data_type}, but is {type(value)}")
                debug_metadata_tests(f"[red]error")
                continue
            debug_metadata_tests(f"[green]success")

def consolidate_metadata(metadata_files: list):
    assert len(metadata_files) > 0, "Expected at least one metadata file!"
    metadata = {}
    for meta_file in metadata_files:
        with open(meta_file) as f:
            contents = yaml.safe_load(f)
        metadata.update(contents)
    assert "sensors" in metadata.keys()
    assert "platforms" in metadata.keys()
    assert "global" in metadata.keys()
    assert "variables" in metadata.keys()
    return metadata


def generate_dataset(data_files: list, metadata_files: list, output: str, log: logging.Logger, keep_names=False):
    """
    Generates an EMSO-compliant NetCDF dataset from the input data and metadata
    """
    log = LoggerSuperclass(log, "VLD")

    log.info(f"Generating NetCDF dataset {output}")
    log.debug("Checking arguments...")
    assert_type(data_files, list)
    [assert_type(f, str) for f in data_files]
    [assert_type(f, str) for f in metadata_files]
    assert len(metadata_files) > 0, "Expected at least one metadata file!"


    metadata = consolidate_metadata(metadata_files)

    if len(data_files) > 0:
        dataframes = [load_data(d) for d in data_files]
        df = pd.concat(dataframes)
        pass
    else:
        columns = {
            "time": pd.Series(dtype='datetime64[ns]'),
            "depth": pd.Series(dtype='float'),
            "sensor_id": pd.Series(dtype='str'),
            "platform_id": pd.Series(dtype='str')
        }
        for name in metadata["variables"].keys():
            columns[name] = pd.Series(dtype='float')

        if "TIME" in metadata["variables"].keys():
            # Avoid duplicated times
            del columns["time"]

        df = pd.DataFrame(columns)

    _time, _depth, _latitude, _longitude, _sensor_id, _platform_id = get_coordinates_from_dataframe(df)

    log.info("Validating metadata...")
    errors = []
    warnings = []

    # Validate that all sensors, platforms and variables are compliant with the schemas
    validate_metadata(metadata, "global", global_elements, errors, warnings)
    validate_metadata(metadata, "sensors", sensor_elements, errors, warnings)
    validate_metadata(metadata, "platforms", platform_elements, errors, warnings)

    for key, variable in metadata["variables"].items():
        if "variable_type" not in variable.keys():
            vartype = "environmental"
        else:
            vartype = variable["variable_type"]
        if vartype == "environmental":
            validate_metadata(metadata, "variables", environmental_variable_elements, errors, warnings, key=key)
        elif vartype == "biological":
            validate_metadata(metadata, "variables", biological_variable_elements, errors, warnings, key=key)
        elif vartype == "technical":
            validate_metadata(metadata, "variables", technical_variable_elements, errors, warnings, key=key)
        elif vartype == "coordinate":
            validate_metadata(metadata, "variables", technical_variable_elements, errors, warnings, key=key)
        else:
            raise ValueError(f"Variable type '{vartype}' not supported")

    # Validate that global attributes are compliant with the schemas

    for w in warnings:
        log.warning(w)

    for e in errors:
        log.error(e)

    if len(errors) > 0:
        log.error("Got errors in dataset generation", exception=ValueError)

    wf = WaterFrame(df, metadata)
    wf.to_netcdf(output, keep_names=keep_names)
