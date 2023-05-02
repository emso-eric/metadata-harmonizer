#!/usr/bin/env python3
"""

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 13/4/23
"""

from argparse import ArgumentParser
import rich
from erddap.datasets_xml import generate_datsets_xml
from metadata.autofill import expand_minmeta
from metadata.dataset import load_csv_data, add_coordinates, ensure_coordinates, update_waterframe_metadata, \
    merge_waterframes, export_to_netcdf, load_nc_data
from metadata.minmeta import generate_min_meta_template, load_min_meta, load_full_meta
from metadata import EmsoMetadata


def generate_metadata(data_files: list, folder):
    """
    Generate the metadata templates for the input file in the target folder
    """
    # If metadata and generate
    for file in data_files:
        rich.print(f"generating minimal metadata template for {file}")
        wf = load_csv_data(file)
        generate_min_meta_template(wf, folder)
    rich.print(f"[green]Please edit the following files and run the generator with the -m option!")



def generate_datasets(data_files, metadata_files: list):
    """
    Merge data fiiles and metadata files into a NetCDF dataset according to EMSO specs. If provided, depths, lats and
    longs will be added to the dataset as dimensions.
    """
    emso = EmsoMetadata()
    waterframes = []
    for i in range(len(data_files)):
        datafile = data_files[i]
        metafile = metadata_files[i]

        if datafile.endswith(".csv"):
            rich.print(f"Loading CSV file {datafile}...")
            wf = load_csv_data(datafile)
        elif datafile.endswith(".nc"):
            wf = load_nc_data(datafile)

        if metafile.endswith(".min.json"):
            rich.print(f"Loading a minimal metadata file {metafile}...")
            minmeta = load_min_meta(wf, metafile, emso)
            if "coordinates" in minmeta.keys():
                lat = minmeta["coordinates"]["latitude"]
                lon = minmeta["coordinates"]["longitude"]
                depth = minmeta["coordinates"]["depth"]
                wf = add_coordinates(wf, lat, lon, depth)
            ensure_coordinates(wf)  # make sure that all coordinates are set
            metadata = expand_minmeta(wf, minmeta, emso)

        elif metafile.endswith(".full.json"):
            rich.print(f"Loading a full metadata file {metafile}...")
            metadata = load_full_meta(wf, metafile)

        wf = update_waterframe_metadata(wf, metadata)
        waterframes.append(wf)
    return waterframes


if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument("-v", "--verbose", action="store_true", help="Shows verbose output", default=False)
    argparser.add_argument("-d", "--data", type=str, help="List of data files (CSV or NetCDF)", required=True,
                           nargs="+")
    argparser.add_argument("-m", "--metadata", type=str, help="List of JSON metadata documents", required=False,
                           nargs="+")
    argparser.add_argument("-g", "--generate", type=str, help="Generates metadata templates in the specified folder",
                           required=False)

    argparser.add_argument("-o", "--output", type=str, help="Output NetCDF file", required=False, default="out.nc")
    argparser.add_argument("-x", "--xml", action="store_true", help="Generate datasets.xml chunkd", required=False)

    args = argparser.parse_args()

    if args.generate and args.metadata:
        raise ValueError("--metadata and --generate cannot be used at the same time!")

    if not args.generate and not args.metadata:
        raise ValueError("--metadata OR --generate option ust be used!")

    # If metadata and generate
    if args.generate:
        rich.print("[blue]Generating metadata templates...")
        generate_metadata(args.data, args.generate)
        exit()

    waterframes = generate_datasets(args.data, args.metadata)
    wf = merge_waterframes(waterframes)

    if args.output:
        export_to_netcdf(wf, args.output)

    if args.xml:
        generate_datsets_xml(wf)

