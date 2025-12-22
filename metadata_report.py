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
    argparser.add_argument("-l", "--list", action="store_true", help="List dataset in ERDDAP and exit")
    argparser.add_argument("-p", "--print", action="store_true", help="Just pretty-print the metadata")
    argparser.add_argument("-v", "--verbose", action="store_true", help="Shows more info")
    argparser.add_argument("-s", "--save-metadata", type=str, help="Save dataset's metadata into the specified folder",
                           default="")
    argparser.add_argument("-o", "--output", type=str, help="file to store the report of all the datasets", default="")
    argparser.add_argument("-r", "--report", action="store_true", help="Generate a CSV file for every test")
    argparser.add_argument("-c", "--clear", action="store_true", help="Clears downloaded files")
    argparser.add_argument("-i", "--ignore-ok", action="store_true", help="do not show tests with positive outcome")
    argparser.add_argument("-t", "--table", action="store_true", help="prints the results in excel compatible table")
    argparser.add_argument("-V", "--variables", nargs="+", help="Run test only for a variable subset", default=[])
    argparser.add_argument("--specs", type=str, help="Use this file as EMSO Metadata specifications source (use only for development)", default="")

    args = argparser.parse_args()
    metadata_report(
        args.target,
        just_list=args.list,
        just_print=args.print,
        verbose=args.verbose,
        save_metadata=args.save_metadata,
        output=args.output,
        report=args.report,
        clear=args.clear,
        excel_table=args.table,
        specifications=args.specs,
        variables=args.variables,
        ignore_ok=args.ignore_ok
    )
