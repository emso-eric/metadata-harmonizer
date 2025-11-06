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
from ..metadata.waterframe import WaterFrame
from ..metadata.xmlutils import get_element, append_after
from datetime import datetime
import rich


def generate_erddap_dataset(wf: WaterFrame, directory, dataset_id, file_access=True):
    """
    Generates a XML chunk to add it into ERDDAP's datasets.xml
    :param wf: waterframe with data and metadata
    :param directory: path where the NetCDF files will be stored
    :param dataset_id: datsetID to identify the dataset
    returns: a string containing the datasets.xml chunk to setup the dataset
    """
    assert  isinstance(wf, WaterFrame), f"Expected WaterFrame (got {type(wf)})"
    # dimension_name, data_type, special_attributes
    erddap_dims = [
        ("time", "double", {"units": "seconds since 1970-01-01", "time_precision": "1970-01-01T00:00:00Z" }),
        ("depth", "float", {"units": "m"}),
        ("latitude", "float", {}),
        ("longitude", "float", {})
        # ("platform_id", "String", {}),
        # ("sensor_id", "byte", {})
    ]

    erddap_qc = [v for v in wf.data.columns if v.endswith("_QC")]


    if "infoUrl" in wf.metadata.keys(): # If infoURL not set, use the edmo uri
        info_url = wf.metadata["infoUrl"]
    elif "institution_edmo_uri" in wf.metadata.keys():
        info_url = wf.metadata["institution_edmo_uri"]
    else:
        info_url = "https://edmo.seadatanet.org/report/" + str(wf.metadata["institution_edmo_code"])

    additional_attributes = {}
    cf_feature_type = wf.metadata["featureType"]

    if  cf_feature_type == "timeSeries":
        cdm_data_type = "timeSeries"
        additional_attributes["cdm_timeseries_variables"] = "platform_id,sensor_id,latitude,longitude,depth"
        position_vars = []
        if "precise_latitude" in wf.data.columns and "precise_longitude" in wf.data.columns:
            position_vars = ["precise_latitude", "precise_longitude"]

        subset_vars_str = ",".join(["platform_id", "sensor_id", "depth"] + erddap_qc + position_vars)


    elif  cf_feature_type == "timeSeriesProfile":
        cdm_data_type = "timeSeriesProfile"
        additional_attributes["cdm_timeseries_variables"] = "platform_id,latitude,longitude"
        additional_attributes["cdm_profile_variables"] = "time,sensor_id"
        subset_vars_str = ",".join(["platform_id", "sensor_id", "depth"] + erddap_qc)

    elif  cf_feature_type == "trajectory":
        cdm_data_type = "trajectory"
        additional_attributes["cdm_trajectory_variables"] = "platform_id"
        subset_vars_str = ",".join(["platform_id", "sensor_id"] + erddap_qc)
    elif  cf_feature_type == "trajectoryProfile":
        cdm_data_type = "trajectory"
        additional_attributes["cdm_trajectory_variables"] = "platform_id"
        subset_vars_str = ",".join(["platform_id", "sensor_id"] + erddap_qc)

    else:
        raise ValueError(f"Unimplemented CF feature type {cf_feature_type}")

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
    <recursive>true</recursive>    
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
        new_element = etree.Element("att", attrib={"name": key})
        add_attributes = get_element(root, "addAttributes")
        new_element.text = value
        append_after(add_attributes, "att", new_element)

    for varname, dtype, attrs in erddap_dims:
        add_variable(root, varname, varname, dtype, attributes=attrs)

    dimension_names = [v[0] for v in erddap_dims]

    # Convert from Pandas dtype to ERDDAP dtype
    for v in wf.data.columns:
        if v in dimension_names:
            continue
        if v.endswith("_QC"):
            dtype = "ubyte"
        elif pd.api.types.is_float_dtype(wf.data[v].dtype):
            dtype = "float"
        elif pd.api.types.is_integer_dtype(wf.data[v].dtype):
            dtype = "int"
        elif pd.api.types.is_string_dtype(wf.data[v].dtype):
            dtype = "String"
        else:
            raise ValueError(f"Unimplemented data type {wf.data[v].dtype}")

        add_variable(root, v, v, dtype, attributes={})

    for sensor in wf.sensors.values():
        name = sensor["sensor_id"]
        add_variable(root, name, name, "String", attributes={})

    for platform in wf.platforms.values():
        name = platform["platform_id"]
        add_variable(root, name, name, "String", attributes={})

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

    root.append(dataset_root)
    with open(filename, "w") as f:
        xml = etree.tostring(tree, encoding="UTF-8", pretty_print=True, xml_declaration=True)
        s = xml.decode()
        f.write(s)













