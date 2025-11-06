#!/usr/bin/env python3
"""

Generates NetCDF files based on CSV files and input from the user

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 13/4/23
"""

from argparse import ArgumentParser
import yaml
from src.emso_metadata_harmonizer import generate_dataset
from src.emso_metadata_harmonizer.metadata.utils import setup_log


if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument("-v", "--verbose", action="store_true", help="Shows verbose output", default=False)
    argparser.add_argument("-d", "--data", type=str, help="list of data files (CSV or NetCDF)", required=False,
                           nargs="+", default=[])
    argparser.add_argument("-m", "--metadata", type=str, help="metadata yaml files", required=True, nargs="+")
    argparser.add_argument("-M", "--metadata-only", help="Generate only a _meta.nc file", action="store_true")
    argparser.add_argument("-o", "--output", type=str, help="Output NetCDF file", required=False, default="out.nc")
    argparser.add_argument("--clear", action="store_true", help="Clears all downloads", required=False)

    args = argparser.parse_args()
    log = setup_log("emh", "log")

    generate_dataset(args.data, args.metadata,  args.output, log, meta_only=args.metadata_only)
