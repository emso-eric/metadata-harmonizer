#!/usr/bin/env python3
"""
Automatically generates datasets.xml configuration to serve NetCDFs file through ERDDAP


author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 15/5/23
"""
import logging
from argparse import ArgumentParser
from src.emso_metadata_harmonizer.erddap import erddap_config
from src.emso_metadata_harmonizer.metadata.utils import setup_log
import yaml


if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument("file", type=str, help="NetCDF file")
    argparser.add_argument("dataset_id", type=str, help="Dataset ID")
    argparser.add_argument("source", type=str, help="Path to the folder where the data files are stored")
    argparser.add_argument("-o", "--output", type=str, help="Name of the output XML file", default="")
    argparser.add_argument("-x", "--xml", type=str, help="Path to the datasets.xml file, new dataset will be overwritten or appended", default="")
    argparser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    argparser.add_argument("-m", "--mapping", type=str, help="Create a metadata-only NetCDF file to overwrite NetCDF's parameters", default="")
    argparser.add_argument("-r", "--regex", type=str,
                           help="Regex expression to be passed to ERDDAP's fileNameRegexCreate (default .*)", default=".*")

    args = argparser.parse_args()
    log = setup_log("emh", "log")
    if args.verbose:
        log.setLevel(logging.DEBUG)

    nc_file = args.file

    mapping = {}
    if args.mapping:
        with open(args.mapping) as f:
            mapping = yaml.safe_load(f)

    erddap_config(args.file, args.dataset_id, args.source, output=args.output, datasets_xml_file=args.xml, mapping=mapping, filename_regex=args.regex)
