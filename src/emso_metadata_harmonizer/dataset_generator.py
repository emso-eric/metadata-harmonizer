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

from .metadata.autofill import autofill_waterframe
from .metadata.dataset import load_data
from .metadata.minmeta import generate_min_meta_template, generate_full_metadata, load_metadata
from .metadata import EmsoMetadata
from .metadata.utils import assert_type, LoggerSuperclass
from .metadata.waterframe import WaterFrame, merge_waterframes


def generate_metadata(data_files: list, folder):
    """
    Generate the metadata templates for the input file in the target folder
    """
    # If metadata and generate
    for file in data_files:
        rich.print(f"generating minimal metadata template for {file}")
        wf = load_data(file)
        if file.endswith(".csv"):  # For CSV always generate a minimal metdata file
            generate_min_meta_template(wf, folder)
        elif file.endswith(".nc"):
            generate_full_metadata(wf, folder)

    rich.print(f"[green]Please edit the following files and run the generator with the -m option!")


def generate_datasets(data_list: list, metadata_list: list, emso_metadata: EmsoMetadata):
    """
    Merge data files and metadata files into a NetCDF dataset according to EMSO specs. If provided, depths, lats and
    longs will be added to the dataset as dimensions.
    """
    assert len(metadata_list) == len(data_list), "Expected the same amount of data and metaadata elements!"
    if emso_metadata:
        emso = emso_metadata
    else:
        emso = EmsoMetadata()
    waterframes = []
    for data_file, meta_file in zip(data_list, metadata_list):
        meta = load_metadata(meta_file, emso)
        df = load_data(data_file)
        wf = WaterFrame(df, meta)
        waterframes.append(wf)
    return waterframes


global_elements = (
    # Array with attribute_name, type, mandatory (True, False), additional_checks
    ("title", str, True),
    ("summary", str, False),
    ("institution", str, True),
    ("institution_edmo_code", str, False),
    ("Conventions", str, False),
    ("update_interval", str, True),
    ("site_code", str, True),
    ("emso_facility", str, False),
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
    ("emso_ontology_uri", str, False),
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
    ("sensor_model", str, False),
    ("sensor_model_uri", str, True),
    ("sensor_SeaVoX_L22_code", str, False),
    ("sensor_manufacturer_uri", str, True),
    ("sensor_manufacturer_urn", str, False),
    ("sensor_manufacturer", str, False),
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

def generate_dataset(data_files: list, metadata_files: list, output: str, log: logging.Logger):
    """
    Generates an EMSO-compliant NetCDF dataset from the input data and metadata
    """
    log.info(f"Generating NetCDF dataset {output}")
    log.debug("Checking arguments...")
    assert_type(data_files, list)
    [assert_type(f, str) for f in data_files]
    [assert_type(f, str) for f in metadata_files]
    assert len(data_files) > 0, "Expected at least one data file!"
    assert len(metadata_files) > 0, "Expected at least one metadata file!"


    metadata = {}
    for meta_file in metadata_files:
        with open(meta_file) as f:
            contents = yaml.safe_load(f)
        metadata.update(contents)

    assert_type(metadata, dict)
    assert "sensors" in metadata.keys()
    assert "platforms" in metadata.keys()
    assert "global" in metadata.keys()
    assert "variables" in metadata.keys()

    log = LoggerSuperclass(log, "VLD")
    errors = []
    warnings = []

    log.info("Validating metadata...")
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

        else:
            raise ValueError(f"Variable type '{vartype}' not supported")

    # Validate that global attributes are compliant with the schemas

    for w in warnings:
        log.warning(w)

    for e in errors:
        log.error(e)

    if len(errors) > 0:
        log.error("Got errors in dataset generation", exception=ValueError)



    dataframes = [load_data(d) for d in data_files]
    df = pd.concat(dataframes)
    wf = WaterFrame(df, metadata)
    wf.to_netcdf(output)

