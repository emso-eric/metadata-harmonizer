#!/usr/bin/env python3
"""
Generates a chunk for the datasets.xml file

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 28/4/23
"""
import os
import shutil
import lxml.etree as etree
import pandas as pd
import yaml
from ..metadata.metadata_templates import coordinate_default_name
from ..metadata.waterframe import WaterFrame
from ..metadata.xmlutils import get_element, append_after, get_elements
from datetime import datetime
import rich



def erddap_config(file: str, dataset_id: str, source_path: str, output: str = "", datasets_xml_file: str = "",
                  mapping: dict={}):
    """
    Configures an ERDDAP dataset based on an input NetCDF file

    :param file: NetCDF file to read metadata from
    :param dataset_id: ID assigned to the dataset in ERDDAP
    :param source_path: Source path where ERDDAP will look for nc files
    :param output: Write the XML chunk into a file
    :param datasets_xml_file: If the path to the datasets.xml is passed here, it will automatically be updated with the new dataset
    :param mapping: mapping file with the source/destination links for mapped datasets
    :param params: Force the use of file as the metadata source in ERDDAP

    """
    wf = WaterFrame.from_netcdf(file)

    if isinstance(mapping, str) and mapping:
        with open(mapping) as f:
            mapping = yaml.safe_load(f)

    xml_chunk = generate_erddap_dataset(wf, source_path, dataset_id=dataset_id, mapping=mapping)

    if output:
        with open(output, "w") as f:
            f.write(xml_chunk)

    if datasets_xml_file:
        add_dataset(datasets_xml_file, xml_chunk)

    if not datasets_xml_file and not output:
        rich.print(xml_chunk)

def get_erddap_data_type(series: pd.Series):
    # Get the data type
    if series.name.endswith("_QC"):
        dtype = "ubyte"
    elif pd.api.types.is_float_dtype(series.dtype):
        dtype = "double"
    elif pd.api.types.is_integer_dtype(series.dtype):
        dtype = "int"
    elif pd.api.types.is_string_dtype(series.dtype):
        dtype = "String"
    elif pd.api.types.is_datetime64_ns_dtype(series.dtype):
        dtype = "double"
    return dtype

def generate_erddap_dataset(wf: WaterFrame, directory, dataset_id, file_access=True, mapping={}):
    """
    Generates a XML chunk to add it into ERDDAP's datasets.xml. The Variables are going to be ordered as follows:
    1. Coordinates
    2. Variables
    3. Quality Control

    :param wf: WaterFrame with data and metadata
    :param directory: path where the NetCDF files will be stored
    :param dataset_id: datsetID to identify the dataset
    :param file_access: toggles on/off the direct file access
    :param mapping: dictionary containing mapping info to rename variables and/or override attributes
    :param params: extra global configuration options
    returns: a string containing the datasets.xml chunk to setup the dataset
    """
    assert isinstance(wf, WaterFrame), f"Expected WaterFrame (got {type(wf)})"

    assert isinstance(directory, str), f"Expected str for directory (got {type(directory)})"

    vocab = wf.vocabulary
    if mapping:
        # convert from array to a dict with source as the key
        rich.print(f"[cyan]Using Mapping")
        var_mapping = {d["source"]: d for d in mapping["mapping"]["variables"]}
        attr_mapping = mapping["mapping"]["attributes"]
    else:
        var_mapping = {}
        attr_mapping = {}

    # get the coordinate names from the WaterFrame
    _time, _depth, _latitude, _longitude, _sensor_id, _platform_id = wf.get_coordinate_names()

    # all_variables hosts the list of all variables that will be used to generate its ERDDAP config
    # source = [source, destination, type, attributes, all_attributes]
    #   source: ERDDAP source name
    #   destination: ERDDAP destination name
    #   attributes: attributes to be explicitly overwritten
    #   all_attributes: rest of the attributes, attached here to simplify search
    all_variables = {}


    #---- Step 1. update the vocabulary with the mapping metadata
    for varname, var_meta in vocab.items():
        attributes = {}
        if varname in var_mapping.keys():
            # If we have a mapping for this variable, set the destination and merge the attributes
            var_meta.update(var_mapping[varname]["attributes"])

    #---- Step 2. Create new entries in vocabulary for the missing metadata
    for varname, mapping in var_mapping.items():
        if varname not in wf.vocabulary.keys():
            rich.print(f"[grey42]Variable {varname} not defined in WaterFrame, using mapping config")
            attributes = {}
            if "attributes" in mapping.keys():
                attributes = mapping["attributes"]

            source = mapping["source"]
            vocab[source] = attributes

    #---- Step 3. Create the all_variables structure
    for varname, value in vocab.items():
        source = varname
        attributes = {}  # By default, do not modify attributes
        if varname in var_mapping.keys():
            # If we have a mapping for this variable, set the destination and merge the attributes
            destination = var_mapping[varname]["destination"]
            attributes = var_mapping[varname]["attributes"]
        else:
            try:
                # Get the default coordinate name
                destination = coordinate_default_name(source)
            except LookupError:
                destination = varname

        if varname in wf.data.columns:
            # If we have a data type use the dtype from the data type
            dtype = get_erddap_data_type(wf.data[varname])

        elif varname in var_mapping.keys():
            try:
                dtype = var_mapping[varname]["dataType"]
            except KeyError:
                raise ValueError(f"Variable '{varname}' dataType must be defined in the mapping")
        else:
            raise ValueError(f"Variable '{varname}' dataType not found in DataFrame nor in mapping")

        all_variables[destination] = [source, destination, dtype, attributes, vocab[varname]]


    # Now, let's apply missing mapping
    for key, m in var_mapping.items():
        if key not in all_variables.keys():
            attributes = {}
            if "attributes" in m.keys():
                attributes = m["attributes"]
            all_variables[m["destination"]] = [m["source"], m["destination"], "float", attributes, attributes]


    # Make sure that ALL QC variables have the proper data type
    for varname, var in all_variables.items():
        if varname.endswith("_QC"):
            var[2] = "ubyte"  # make sure data type is byte
            if "variable_type" not in vocab[varname].keys() or vocab[varname]["variable_type"] != "quality_control":
                var[3]["variable_type"] = "quality_control"
            all_variables[varname] = var

    # Now let's organize all variables in the following order:
    #  1. coordinates
    #  2. variables
    #  3. quality control
    #  4. metadata (sensors and platforms)

    coordinates = []
    variables =  []
    quality_control = []
    sensors = []
    platforms = []
    others = []

    def get_variable_config(key, dictionary):
        if key not in all_variables.copy().keys():
            return
        dictionary.append(all_variables.pop(key))

    get_variable_config("time", coordinates)
    get_variable_config("depth", coordinates)
    get_variable_config("latitude", coordinates)
    get_variable_config("longitude", coordinates)
    get_variable_config("sensor_id", coordinates)
    get_variable_config("platform_id", coordinates)
    # Now, get optional coordinates
    get_variable_config("precise_latitude", coordinates)
    get_variable_config("precise_longitude", coordinates)
    get_variable_config("deployment_latitude", coordinates)
    get_variable_config("deployment_longitude", coordinates)

    # Get variables
    for varname in list(all_variables.keys()):
        try:
            vartype = vocab[varname]["variable_type"]
        except KeyError:
            rich.print(f"[yellow]WARNING: Variable {varname} does not have a defined variable type")
            vartype = ""

        if vartype == "coordinate":
            get_variable_config(varname, coordinates)
        elif vartype in ["environmental", "technical", "biological"]:
            get_variable_config(varname, variables)
        elif vartype == "quality_control":
            get_variable_config(varname, quality_control)

        elif vartype == "sensor":
            get_variable_config(varname, sensors)
        elif vartype == "platform":
            get_variable_config(varname, platforms)
        else:
            get_variable_config(varname, others)

    # Now put the rest with a warning
    for varname in all_variables.copy().keys():
        rich.print(f"[yellow]WARNING: variable {varname} does not have a proper 'variable_type' attribute!")
        get_variable_config(varname, others)


    all_variables = coordinates + variables + quality_control + sensors + platforms + others
    rich.print(f"[yellow]WARNING CHECK ANCILLARY_VARIABLES AND QC VARIABLE NAMES!")

    if "infoUrl" in wf.metadata.keys():  # If infoURL not set, use the edmo uri
        info_url = wf.metadata["infoUrl"]
    elif "institution_edmo_uri" in wf.metadata.keys():
        info_url = wf.metadata["institution_edmo_uri"]
    else:
        info_url = "https://edmo.seadatanet.org/report/" + str(wf.metadata["institution_edmo_code"])

    additional_attributes = {}
    cf_feature_type = wf.metadata["featureType"]

    qc_vars = [qc[1] for qc in quality_control]  # get QC destination names
    all_variable_names = [a[1] for a in all_variables]

    if cf_feature_type == "timeSeries":
        cdm_data_type = "timeSeries"
        additional_attributes["cdm_timeseries_variables"] = "platform_id,sensor_id,latitude,longitude,depth"
        position_vars = []
        if "precise_latitude" in  all_variable_names and "precise_longitude" in all_variable_names:
            position_vars += ["precise_latitude", "precise_longitude"]
        elif "nominal_latitude" in all_variable_names and "nominal_longitude" in all_variable_names:
            position_vars += ["nominal_latitude", "nominal_longitude"]

        subset_vars_str = ",".join(["platform_id", "sensor_id", "depth"] + qc_vars + position_vars)

    elif cf_feature_type == "timeSeriesProfile":
        cdm_data_type = "timeSeriesProfile"
        additional_attributes["cdm_timeseries_variables"] = "platform_id,latitude,longitude"
        additional_attributes["cdm_profile_variables"] = "time,sensor_id"
        subset_vars_str = ",".join(["platform_id", "sensor_id", "depth"] + qc_vars)

    elif cf_feature_type == "trajectory":
        cdm_data_type = "trajectory"
        additional_attributes["cdm_trajectory_variables"] = "platform_id"
        subset_vars_str = ",".join(["platform_id", "sensor_id"] + qc_vars)
    elif cf_feature_type == "trajectoryProfile":
        cdm_data_type = "trajectory"
        additional_attributes["cdm_trajectory_variables"] = "platform_id"
        subset_vars_str = ",".join(["platform_id", "sensor_id"] + qc_vars)

    else:
        raise ValueError(f"Unimplemented CF feature type {cf_feature_type}")
    if attr_mapping:
        additional_attributes.update(attr_mapping)  # Add mapping global attributes

    if file_access:
        file_access_str = "true"
    else:
        file_access_str = "false"

    x = f"""    
<dataset type="EDDTableFromMultidimNcFiles" datasetID="{dataset_id}" active="true">
    <reloadEveryNMinutes>10080</reloadEveryNMinutes>
    <updateEveryNMillis>10000</updateEveryNMillis>
    <fileDir>{directory}</fileDir>
    <fileNameRegex>.*</fileNameRegex>
    <recursive>false</recursive>    
    <pathRegex>.*</pathRegex>
    <metadataFrom>last</metadataFrom>
    <metadataFrom>last</metadataFrom>
    <standardizeWhat>0</standardizeWhat>
    <removeMVRows>true</removeMVRows>
    <accessibleViaFiles>{file_access_str}</accessibleViaFiles>
    <sortFilesBySourceNames></sortFilesBySourceNames>
    <fileTableInMemory>false</fileTableInMemory>
    <addAttributes>
        <att name="_NCProperties">null</att>
        <att name="cdm_data_type">{cdm_data_type}</att>
        <att name="infoUrl">{info_url}</att>                
        <att name="sourceUrl">(local files)</att>
        <att name="standard_name_vocabulary">CF Standard Name Table v70</att>
        <att name="subsetVariables">{subset_vars_str}</att> 
    </addAttributes>        
</dataset>
    """
    tree = etree.ElementTree(etree.fromstring(x))
    root = tree.getroot()

    # Add additional global attributes
    for key, value in additional_attributes.items():
        add_attribute = get_element(root, "addAttributes")
        new_element = etree.SubElement(add_attribute, "att", attrib={"name": key})
        new_element.text = value

    for source, destination, dtype, attrs, _ in all_variables:
        add_variable(root, source, destination, dtype, attributes=attrs)

    etree.indent(root, space="    ", level=0)  # force indentation
    return serialize(tree)

def read_xml(filename):
    """
    Reads a XML file and returns the root element
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(filename, parser)  # load from template
    root = tree.getroot()
    return root


def serialize(tree):
    etree.indent(tree, space="  ", level=0)
    return etree.tostring(tree, encoding="unicode", pretty_print=True, xml_declaration=False)


def prettyprint_xml(x):
    """
    produces a pretty print of an etree
    """
    etree.indent(x, space="  ", level=1)


def add_variable(root, source, destination, datatype, attributes: dict = {}):

    """
    Adds a variable to an ERDDAP dataset
    """

    __valid_data_types = ["int", "ubyte", "byte", "double", "float", "String"]

    if datatype not in __valid_data_types:
        raise ValueError(f"Data type '{datatype}' not valid!")

    var = etree.SubElement(root, "dataVariable")
    etree.SubElement(var, "sourceName").text = source
    etree.SubElement(var, "destinationName").text = destination
    etree.SubElement(var, "dataType").text = datatype
    attrs = etree.SubElement(var, "addAttributes")
    for key, value in attributes.items():
        att = etree.SubElement(attrs, "att")
        att.attrib["name"] = key
        att.text = value


def backup_datasets_file(filename):
    """
    Generates a .datasets.xml.YYYMMDD_HHMMSS backup file of the datasets.xml
    """
    assert type(filename) is str, f"expected string, got {type(filename)}"
    basename = os.path.basename(filename)
    directory = os.path.dirname(filename)
    backup = "." + basename + "." + datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(directory, backup)
    shutil.copy2(filename, backup)
    return backup


def add_dataset(filename: str, dataset: str):
    """
    Adds a dataset to an exsiting ERDDAP deployment by modifying the datasets.xml config file
    :param filename: path to datasets.xml file
    :param dataset: string containing the XML configuration for the dataset
    """

    assert type(filename) is str, f"expected string, got {type(filename)}"
    assert type(dataset) is str, f"expected string, got {type(dataset)}"

    backup_datasets_file(filename)
    dataset_tree = etree.ElementTree(etree.fromstring(dataset))
    dataset_root = dataset_tree.getroot()
    dataset_id = dataset_root.attrib["datasetID"]

    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(filename, parser)  # load from template
    root = tree.getroot()

    try:
        e = get_element(root, "dataset", attr="datasetID", attr_value=dataset_id)
        rich.print(f"[yellow]Overwriting existing dataset {dataset_id}!")
        e.getparent().remove(e)  # Remove the old dataset
    except LookupError:
        pass

    comment = etree.Comment(f" ======== Dataset {dataset_id} configuration ========")
    root.append(comment)
    root.append(dataset_root)
    with open(filename, "w") as f:
        xml = etree.tostring(tree, encoding="UTF-8", pretty_print=True, xml_declaration=True)
        s = xml.decode()
        f.write(s)
