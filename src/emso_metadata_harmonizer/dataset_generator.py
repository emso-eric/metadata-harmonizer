#!/usr/bin/env python3
"""

Generates NetCDF files based on CSV files and input from the user

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 13/4/23
"""
import copy
import logging
import rich
import pandas as pd
import yaml

from .metadata import EmsoMetadata
from .metadata.dataset import resolve_data_source
from .metadata.utils import assert_type, EMH_LOGGER_NAME
from .metadata.waterframe import WaterFrame, get_coordinates_from_dataframe

logger = logging.getLogger(EMH_LOGGER_NAME)

global_elements = (
    # Array with attribute_name, type, mandatory (True, False), additional_checks
    ("title", str, True),
    ("summary", str, False),
    ("institution", str, True),
    ("institution_edmo_code", str, True),
    ("institution_ror_uri", str, True),
    ("Conventions", str, False),
    ("update_interval", str, True),
    ("emso_site_name", str, True),
    ("emso_regional_facility_name", str, False),
    ("source", str, True),
    ("data_type", str, True),
    ("format_version", str, True),
    ("network", str, True),
    ("data_mode", str, True),
    ("projects", str, False),
    ("project_codes", str, False),
    ("principal_investigator", str, True),
    ("principal_investigator_email", str, True),
    ("license", str, True)
)

platform_elements = (
    ("long_name", str, True),
    ("wmo_platform_code", str, False),
    ("emso_platform_name", str, False),
    ("platform_type_name", str, False),
    ("platform_type_uri", str, True),
    ("platform_reference", str, False),
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
    # Multiple: true in the spec (one L05 term per sensing element for a multiparameter probe not
    # covered by a single term) - may be a blank-separated str or, as authored in YAML, a list
    ("sensor_type_uri", (str, list), False),
    ("sensor_type_urn", (str, list), False),
    ("sensor_type_name", (str, list), False),
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

def validate_metadata(metadata: dict, section: str, rules: tuple, errors: list, warnings: list, infos: list, key=""):
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
                    infos.append(f"{section}:{element_id} Missing optional attribute '{key}'")
                    debug_metadata_tests(f"[grey42]info")
                continue
            value = data[key]
            if not isinstance(value, data_type):
                errors.append(f"{section}:{element_id}:{key} must be {data_type}, but is {type(value)}")
                debug_metadata_tests(f"[red]error")
                continue
            debug_metadata_tests(f"[green]success")

def resolve_metadata_source(source) -> dict:
    """
    Accepts either a path to a YAML metadata file or an in-memory dict, returning a dict ready for
    merging. A dict is deep-copied so the in-place updates generate_dataset() makes later (e.g.
    consolidate_keywords) never mutate the caller's object, so it can be reused across calls.
    """
    if isinstance(source, dict):
        return copy.deepcopy(source)
    if isinstance(source, str):
        with open(source) as f:
            return yaml.safe_load(f)
    raise TypeError(f"metadata source must be a file path (str) or a dict, got {type(source)}")


def consolidate_metadata(metadata_files: list):
    assert len(metadata_files) > 0, "Expected at least one metadata file!"
    metadata = {}
    for meta_file in metadata_files:
        contents = resolve_metadata_source(meta_file)
        metadata.update(contents)
    assert "sensors" in metadata.keys(), f"Sensors not found in metadata"
    assert "platforms" in metadata.keys(), f"Platforms not found in metadata"
    assert "global" in metadata.keys(), "Global metadata not found in metadata"
    assert "variables" in metadata.keys(), "Variables not found in metadata"
    return metadata


def generate_dataset(data_files, metadata_files, output: str, keep_names=False, no_keywords=False,
                     ignore_extra_cols=False, specs_version="latest", clear_downloads=False):
    """
    Generates an EMSO-compliant NetCDF dataset from the input data and metadata
    :param data_files: csv/NetCDF data file path(s), as a single path or a list. Also accepts a
        pandas DataFrame (or a list mixing paths and DataFrames) to skip the disk read when the
        data is already in memory.
    :param metadata_files: metadata yaml file path(s), as a single path or a list. Also accepts a
        dict (or a list mixing paths and dicts) to skip the disk read when the metadata is already
        in memory.
    :param output: output NetCDF file
    :param no_keywords: Do not guess additional keywords based on existing metadata
    :param ignore_extra_cols: Ignore all data columns not listed in metadata
    :param keep_names: whether to keep the names of the coordinates, by default convert coordinate names to lowercase
    :param specifications: Use a local EMSO_Metadata_Specifications file, use only for development!
    """

    if clear_downloads:
        EmsoMetadata.clear_downloads()

    logger.info(f"Generating NetCDF dataset {output}")
    logger.debug("Checking arguments...")

    if not isinstance(data_files, list):
        data_files = [data_files]
    if not isinstance(metadata_files, list):
        metadata_files = [metadata_files]

    [assert_type(f, (str, pd.DataFrame)) for f in data_files]
    [assert_type(f, (str, dict)) for f in metadata_files]
    assert len(metadata_files) > 0, "Expected at least one metadata file!"

    metadata = consolidate_metadata(metadata_files)

    if len(data_files) > 0:
        dataframes = [resolve_data_source(d) for d in data_files]
        df = pd.concat(dataframes)
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

    logger.info("Validating metadata...")
    errors = []
    warnings = []
    infos = []

    # Validate that all sensors, platforms and variables are compliant with the schemas
    validate_metadata(metadata, "global", global_elements, errors, warnings, infos)
    validate_metadata(metadata, "sensors", sensor_elements, errors, warnings, infos)
    validate_metadata(metadata, "platforms", platform_elements, errors, warnings, infos)

    for key, variable in metadata["variables"].items():
        if "variable_type" not in variable.keys():
            vartype = "environmental"
        else:
            vartype = variable["variable_type"]
        if vartype == "environmental":
            validate_metadata(metadata, "variables", environmental_variable_elements, errors, warnings, infos, key=key)
        elif vartype == "biological":
            validate_metadata(metadata, "variables", biological_variable_elements, errors, warnings, infos, key=key)
        elif vartype == "technical":
            validate_metadata(metadata, "variables", technical_variable_elements, errors, warnings, infos,  key=key)
        elif vartype == "coordinate":
            validate_metadata(metadata, "variables", technical_variable_elements, errors, warnings, infos,  key=key)
        else:
            raise ValueError(f"Variable type '{vartype}' not supported")

    # Validate that global attributes are compliant with the schemas

    for i in infos:
        logger.info(i)

    for w in warnings:
        logger.warning(w)

    for e in errors:
        logger.error(e)

    if len(errors) > 0:
        logger.error("Got errors in dataset generation")

    if specs_version:
        EmsoMetadata.set_version(specs_version)

    wf = WaterFrame(df, metadata, ignore_extra_cols=ignore_extra_cols)
    wf.consolidate_keywords(expand=not no_keywords)
    wf.to_netcdf(output, keep_names=keep_names)
