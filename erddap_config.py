#!/usr/bin/env python3
"""
Automatically generates datasets.xml configuration to serve NetCDFs file through ERDDAP


author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 15/5/23
"""

from argparse import ArgumentParser
from src.emso_metadata_harmonizer import erddap_config

if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument("file", type=str, help="NetCDF file")
    argparser.add_argument("dataset_id", type=str, help="Dataset ID")
    argparser.add_argument("source", type=str, help="Path to the folder where the data files are stored")
    argparser.add_argument("-o", "--output", type=str, help="Name of the output XML file", default="")
    argparser.add_argument("-x", "--xml", type=str, help="Path to the datasets.xml file, new dataset will be overwritten or apended", default="")
    args = argparser.parse_args()

    erddap_config(args.file, args.dataset_id, args.source, output=args.output, datasets_xml_file=args.xml)

