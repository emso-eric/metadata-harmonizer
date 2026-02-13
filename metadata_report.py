#!/usr/bin/env python3
"""
This python project connects to an ERDDAP service and ensures that all listed datasets are compliant with the EMSO
Harmonization Guidelines.

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 23/2/23
"""
from argparse import ArgumentParser
from src.emso_metadata_harmonizer import metadata_report

if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument("target", type=str, help="ERDDAP service URL, NetCDF file or JSON metadata file", default="", nargs='?')
    argparser.add_argument("-v", "--verbose", action="store_true", help="Shows more info")
    argparser.add_argument("-o", "--output", type=str, help="file to store the report of all the datasets", default="")
    argparser.add_argument("-c", "--clear", action="store_true", help="Clears downloaded files")
    argparser.add_argument("-i", "--ignore-ok", action="store_true", help="do not show tests with positive outcome")
    argparser.add_argument("-t", "--table", action="store_true", help="prints the results in excel compatible table")
    argparser.add_argument("-V", "--variables", nargs="+", help="Run test only for a variable subset", default=[])
    argparser.add_argument("--specs", type=str, help="Use this file as EMSO Metadata specifications source (use only for development)", default="")

    args = argparser.parse_args()
    metadata_report(
        args.target,
        verbose=args.verbose,
        output=args.output,
        clear=args.clear,
        specifications=args.specs,
        variables=args.variables,
        ignore_ok=args.ignore_ok
    )
