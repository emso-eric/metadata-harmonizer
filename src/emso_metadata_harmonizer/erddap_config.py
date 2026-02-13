#!/usr/bin/env python3
"""
Generates a chunk for the datasets.xml file

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 28/4/23
"""

from .metadata.waterframe import WaterFrame
import yaml
from .erddap.datasets_xml import generate_erddap_dataset, add_dataset
import rich


def erddap_config(file: str, dataset_id: str, source_path: str, output: str = "", datasets_xml_file: str = "",
                  mapping: dict={}, filename_regex=".*"):
    """
    Configures an ERDDAP dataset based on an input NetCDF file compliant with the EMSO Metadata Specifications. The
    configuration is the excerpt of the 'datasets.xml' file (check ERDDAP docs for more info). By default, the XML
    excerpt will be printed in the terminal, but it can be stored in a file (output param) or it can be directly
    added to the datasets.xml file (datasets_xml_file param).

    :param file: NetCDF file to harvest metadata.
    :param dataset_id: ID that will be assigned to the dataset in ERDDAP.
    :param source_path: Source path where ERDDAP will look for nc files. If ERDDAP is deployd within a docker container, this should be the path within the container.
    :param output: Write the XML chunk into a file (empty by default).
    :param datasets_xml_file: If the path to the datasets.xml is passed here, it will automatically be updated with the new dataset (empty by default).
    :param mapping: mapping file with the source/destination links for mapped datasets (empty by default).
    :param filename_regex: Specify special regex rules for the files included in your dataset (default '.*').
    """

    wf = WaterFrame.from_netcdf(file, permissive=True)

    if isinstance(mapping, str) and mapping:
        with open(mapping) as f:
            mapping = yaml.safe_load(f)

    xml_chunk = generate_erddap_dataset(wf, source_path, dataset_id=dataset_id, filename_regex=filename_regex, mapping=mapping)

    if output:
        with open(output, "w") as f:
            f.write(xml_chunk)

    if datasets_xml_file:
        add_dataset(datasets_xml_file, xml_chunk)

    if not datasets_xml_file and not output:
        rich.print(xml_chunk)