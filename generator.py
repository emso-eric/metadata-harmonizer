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
from src.emso_metadata_harmonizer import generate_dataset

if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument("-v", "--verbose", action="store_true", help="Shows verbose output", default=False)
    argparser.add_argument("-d", "--data", type=str, help="List of data files (CSV or NetCDF)", required=True,
                           nargs="+")
    argparser.add_argument("-m", "--metadata", type=str, help="List of JSON metadata documents", required=False,
                           nargs="+")
    argparser.add_argument("-g", "--generate", type=str, help="Generates metadata templates in the specified folder",
                           required=False)
    argparser.add_argument("-a", "--autofill", action="store_true",
                           help="Takes a NetCDF file and tries to autofill its metadata",
                           required=False)
    argparser.add_argument("-o", "--output", type=str, help="Output NetCDF file", required=False, default="")
    argparser.add_argument("--clear", action="store_true", help="Clears all downloads", required=False)

    args = argparser.parse_args()
    generate_dataset(args.data, args.metadata, generate=args.generate, autofill=args.autofill, output=args.output,
                     clear=args.clear)
