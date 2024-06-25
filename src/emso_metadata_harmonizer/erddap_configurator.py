#!/usr/bin/env python3
"""
Automatically generates datasets.xml configuration to serve NetCDFs file through ERDDAP


author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 15/5/23
"""
from .erddap.datasets_xml import generate_erddap_dataset, add_dataset
import rich

from .metadata.dataset import load_data


def erddap_config(file: str, dataset_id: str, source_path: str, output: str = "", datasets_xml_file: str = ""):
    """
    :param file: NetCDF file to be used for the configuration
    :param dataset_id: Dataset ID in ERDDAP
    :param source_path: path where the files for this dataset will be stored
    :param output: If set, the dataset configuration will be stored in a new XML file
    :param datasets_xml: Path to the datasets.xml file. If set the configuration will be appended.
    """
    wf = load_data(file)
    xml_chunk = generate_erddap_dataset(wf, source_path, dataset_id=dataset_id)

    if output:
        with open(output, "w") as f:
            f.write(xml_chunk)

    if datasets_xml_file:
        add_dataset(datasets_xml_file, xml_chunk)

    if not datasets_xml_file and not output:
        rich.print(xml_chunk)
