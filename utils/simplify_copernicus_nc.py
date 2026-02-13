"""
This script takes a NetCDF dataset (Copernicus-like) and performs the following:

* Keeps only CTD data
* Replaces sensor_id from a number to the proper serial number
* Write a new file

"""
import os
import xarray as xr
from argparse import ArgumentParser
import rich
import numpy as np

def simplify_netcdf(infile, outfile):
    ds = xr.open_dataset(infile)
    # Remove non-CTD vars
    keep = ['TIME_QC', 'POSITION_QC', 'DEPTH_QC', 'sensor_id', 'DRYT', 'DRYT_QC', 'TEMP', 'TEMP_QC', 'CNDC', 'CNDC_QC', 'PRES', 'PRES_QC', ]
    for var in list(ds.data_vars):
        if var not in keep:
            del ds[var]

    attributes = ds["DRYT"].attrs
    serial_numbers = attributes["sensor_serial_number"].split("; ")
    sensor_names = attributes["sensor_name"].split("; ")
    sensor_model = attributes["sensor_model"].split("; ")
    sensor_manufacturer = attributes["sensor_manufacturer"].split("; ")
    sensor_manufacturer_uri = attributes["sensor_manufacturer_uri"].split("; ")
    sensor_manufacturer_urn = attributes["sensor_manufacturer_urn"].split("; ")
    sensor_mount = attributes["sensor_mount"].split("; ")
    sensor_reference = attributes["sensor_reference"].split("; ")
    sensor_ids = [(sensor_names[0] + "-SN" + serial_numbers[0]).replace("-", "_").replace(" ", "_")]

    attributes = ds["TEMP"].attrs
    serial_numbers += attributes["sensor_serial_number"].split("; ")
    sensor_names += attributes["sensor_name"].split("; ")
    sensor_model += attributes["sensor_model"].split("; ")
    sensor_manufacturer += attributes["sensor_manufacturer"].split("; ")
    sensor_manufacturer_uri += attributes["sensor_manufacturer_uri"].split("; ")
    sensor_manufacturer_urn += attributes["sensor_manufacturer_urn"].split("; ")
    sensor_mount += attributes["sensor_mount"].split("; ")
    sensor_reference += attributes["sensor_reference"].split("; ")
    sensor_ids += [(sname + "-SN" + sid).replace("-", "_").replace(" ", "_")  for sname, sid in zip(sensor_names[1:], serial_numbers[1:])]

    for i in range(len(sensor_ids)):
        print(f"    - source: \"{sensor_ids[i]}\"")
        print(f"      destination: \"{sensor_ids[i]}\"")
        print(f"      dataType: \"String\"")
        print(f"      attributes:")
        print(f"        variable_type: \"sensor\"")
        print(f"        sensor_model: \"{sensor_model[i]}\"")
        print(f"        sensor_manufacturer: \"{sensor_manufacturer[i]}\"")
        print(f"        sensor_manufacturer_uri: \"{sensor_manufacturer_uri[i]}\"")
        print(f"        sensor_manufacturer_urn: \"{sensor_manufacturer_urn[i]}\"")
        print(f"        sensor_mount: \"{sensor_mount[i]}\"")
        print(f"        sensor_reference: \"{sensor_reference[i]}\"")
        print(f"        serial_number: \"{serial_numbers[i]}\"")
        print("")

    rich.print(f"Sensor IDs: {sensor_ids}")

    unique_vals = np.unique(ds["sensor_id"].values)
    mapping = {}
    for old, new in zip(unique_vals, sensor_ids):
        mapping[old] = new

    def replace_func(x):
        return mapping.get(x, "unknown")

    # Apply to the variable (produces an array of dtype=str)
    ds["sensor_id"] = xr.apply_ufunc(
        np.vectorize(replace_func),
        ds["sensor_id"],
        dask="parallelized",
        output_dtypes=[str]
    )
    ds.to_netcdf(outfile)

if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument("input", help="Input folder with NetCDF files")
    argparser.add_argument("output", help="Folder to store processed NetCDF files")

    args = argparser.parse_args()

    files = [os.path.join(args.input, f) for f in os.listdir(args.input)]
    files = [f for f in files if f.endswith(".nc") and "SIMPLIFIED" not in f]

    if len(files) < 1:
        rich.print("no files to be converted!")
        exit()

    rich.print(f"Convering {len(files)} NetCDF files:")
    for infile in files:
        bname = os.path.basename(infile)
        outfile = bname.replace(".nc", "_SIMPLIFIED.nc")
        outfile = os.path.join(args.output, outfile)
        simplify_netcdf(infile, outfile)
        rich.print("[green]done!")

    rich.print("[green]All files processed!")


