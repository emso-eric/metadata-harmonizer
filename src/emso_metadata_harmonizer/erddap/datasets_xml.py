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
from ..metadata.waterframe import WaterFrame
from ..metadata.dataset import get_variables, set_multisensor, get_dimensions, get_qc_variables
from ..metadata.xmlutils import get_element
from datetime import datetime
import rich


def generate_erddap_dataset(wf: WaterFrame, directory, dataset_id):
    """
    Generates a XML chunk to add it into ERDDAP's datasets.xml
    :param wf: waterframe with data and metadata
    :param directory: path where the NetCDF files will be stored
    :param dataset_id: datsetID to identify the dataset
    returns: a string containing the datasets.xml chunk to setup the dataset
    """
    dimensions = ["TIME", "LATITUDE", "LONGITUDE", "DEPTH"]  # custom dimensional order
    qc_variables = get_qc_variables(wf)

    # ERDDAP will force dimensions to be lowercase, so let's create a dict with source dest like:
    #     { "TIME": "time" }
    erddap_dims = {dim: dim.lower() for dim in dimensions}

    # To ensure that quality control variables match lowercase dimensions another dict like:
    #  {"LATITUDE_QC": "latitude_QC"}
    erddap_qc = {}
    for qcvar in qc_variables:
        source = qcvar.replace("_QC", "")
        if source in dimensions:
            erddap_qc[qcvar] = source.lower() + "_QC"  # ensure dimension is in lower case
        else:
            erddap_qc[qcvar] = qcvar  # do not modify

    # subset variables are QC vars and sensor_id
    subset_vars_str = ", ".join(erddap_qc.values())

    if "$multisensor" not in wf.metadata.keys():
        wf = set_multisensor(wf)

    if wf.metadata["$multisensor"]:
        erddap_dims["SENSOR_ID"] = "sensor_id"
        subset_vars_str += ", sensor_id"  # manually add as subset variable


    if "infoUrl" in wf.metadata.keys(): # If infoURL not set, use the edmo uri
        info_url = wf.metadata["infoUrl"]
    else:
        info_url = wf.metadata["institution_edmo_uri"]


    x = f"""
<dataset type="EDDTableFromMultidimNcFiles" datasetID="{dataset_id}" active="true">
    <reloadEveryNMinutes>10080</reloadEveryNMinutes>
    <updateEveryNMillis>10000</updateEveryNMillis>
    <fileDir>{directory}</fileDir>
    <fileNameRegex>.*</fileNameRegex>
    <recursive>true</recursive>    
    <pathRegex>.*</pathRegex>
    <metadataFrom>last</metadataFrom>
    <standardizeWhat>0</standardizeWhat>
    <removeMVRows>true</removeMVRows>
    <sortFilesBySourceNames></sortFilesBySourceNames>
    <fileTableInMemory>false</fileTableInMemory>
    <addAttributes>
        <att name="_NCProperties">null</att>
        <att name="cdm_data_type">Point</att>
        <att name="infoUrl">{info_url}</att>                
        <att name="sourceUrl">(local files)</att>
        <att name="standard_name_vocabulary">CF Standard Name Table v70</att>
        <att name="subsetVariables">{subset_vars_str}</att> 
    </addAttributes>        
</dataset>
    """
    tree = etree.ElementTree(etree.fromstring(x))
    root = tree.getroot()

    for source, dest in erddap_dims.items():  # already in lowercase
        datatype = "float"
        attrs = {}
        if dest == "time":
            datatype = "double"
            attrs = {
                "units": "seconds since 1970-01-01",
                "time_precision": "1970-01-01T00:00:00Z"
            }
        elif dest == "depth":
            attrs = {
                "units": "m",
            }
        elif dest == "sensor_id":
            datatype = "String"
        add_variable(root, source, dest, datatype, attributes=attrs)

    # Process all data variables
    for v in get_variables(wf):
        add_variable(root, v, v, "float", attributes={})

    for source, dest in erddap_qc.items():
        add_variable(root, source, dest, "byte", attributes={})
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

    __valid_data_types = ["int", "byte", "double", "float", "String"]

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


def backup_datsets_file(filename):
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

    bckp = backup_datsets_file(filename)
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













