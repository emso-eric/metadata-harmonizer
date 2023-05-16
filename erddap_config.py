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
from metadata import load_data
from erddap.datasets_xml import generate_erddap_dataset, add_dataset
import rich

if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument("file", type=str, help="NetCDF file")
    argparser.add_argument("dataset_id", type=str, help="Dataset ID")
    argparser.add_argument("source", type=str, help="Path to the folder where the data files are stored")
    argparser.add_argument("-o", "--output", type=str, help="Name of the output XML file", default="")
    argparser.add_argument("-x", "--xml", type=str, help="Path to the datasets.xml file, new dataset will be overwritten or apended", default="")
    args = argparser.parse_args()

    rich.print("Generating datasets.xml chunk!")
    rich.print(f"[cyan]    NetCDF file: {args.file}")
    rich.print(f"[cyan]     dataset id: {args.dataset_id}")
    rich.print(f"[cyan]  source folder: {args.source}")

    wf = load_data(args.file)
    xml_chunk = generate_erddap_dataset(wf, args.source, dataset_id=args.dataset_id)

    if args.output:
        with open(args.output, "w") as f:
            f.write(xml_chunk)

    if args.xml:
        add_dataset(args.xml, xml_chunk)

    if not args.xml and not args.output:
        rich.print(xml_chunk)


