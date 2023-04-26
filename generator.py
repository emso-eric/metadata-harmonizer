#!/usr/bin/env python3
"""

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 13/4/23
"""
from inspect import currentframe, getframeinfo
import datetime
from argparse import ArgumentParser
import json
import rich
from metadata.netcdf import to_multidim_nc
from metadata import EmsoMetadata, qc_flags, process_metadata, variable_metadata, sensor_metadata, global_metadata, \
    check_mandatory_fields
import datetime
import pandas as pd
import time
import os
import mooda as md
import netCDF4 as nc
import numpy as np
from metadata.metadata_templates import dimension_metadata, quality_control_metadata


def csv_detect_header(filename, separator=","):
    """
    Opens a CSV, reads the last 3 lines and extracts the number of fields. Then it goes back to the beginning and
    detects the first line which is not a header
    """
    with open(filename) as f:
        lines = f.readlines()
    nfields = len(lines[-2].split(separator))
    if nfields < 2 or not (nfields == len(lines[-3].split(separator)) == len(lines[-4].split(separator))):
        raise ValueError("Could not determine number of fields")

    # loop until a first a line with nfields is found
    i = 0
    while len(lines[i].split(separator)) != nfields:
        i += 1

    return i


def set_default_value(data, key, value):
    """
    Sets value key value to a dict if the key is not present
    """
    if key in data.keys() and not data[key]:
        data[key] = value
    return data


def all_equal(values: list):
    """
    checks if all elements in a list are equal
    :param values: input list
    :returns: True/False
    """
    baseline = values[0]
    equals = True
    for element in values[1:]:
        if element != baseline:
            equals = False
            break
    return equals


def consolidate_metadata(dicts: list):
    """
    Consolidates metadata in a list of dicts. All dicts are expected to have the same fields. If all the values are
    equal, keep a single value. If the values are not equal, create a list. However, if it is a sensor_* key, all
    values will be kept.
    """
    keys = [key for key in dicts[0].keys()]  # Get the keys from the first dictionary
    final = {}
    for key in keys:
        values = [d[key] for d in dicts]  # get all the values
        if all_equal(values) and not key.startswith("sensor_"):
            final[key] = values[0]  # get the first element only, all are the same!
        else:
            final[key] = values  # put the full list
    return final


def merge_dicts(strong: dict, weak: dict):
    """
    Merges two dictionaries. If a duplicated field is detected the 'strong' value will prevail
    """
    out = weak.copy()
    out.update(strong)
    return out


class EmsoDataset:
    def __init__(self, data_files):
        """
        This class wraps data and metadata to generate and/or manipulate an EMSO-compliant dataset
        """
        self.emso = EmsoMetadata()
        self.__dimensions = ["time", "latitude", "longitude", "depth"]
        self.__fill_value = -999
        self.multi_sensor = False

        self.data = []  # array of WaterFrame (mooda library)

        for file in data_files:
            if file.lower().endswith(".csv"):
                rich.print(f"[cyan]Loading data from CSV file {file}...")
                df = self.load_csv_data(file)
                wf = md.WaterFrame()
                wf.data = df
                wf.metadata = {}  # global attributes
                wf.metadata["$datafile"] = file

            elif file.lower().endswith(".nc"):
                rich.print("[blue]Loading data from NetCDF file...")
                raise ValueError("Unimplemented")
            else:
                raise ValueError(f"File format .{file.split('.')[-1]} not recognized")

            wf.vocabulary = {}  # variable attributes
            for col in wf.data.columns:
                wf.vocabulary[col] = {}  # initialize empty dicts
            self.data.append(wf)

    def get_qc_variables(self, wf):
        """
        returns a list of QC variables within a waterframe
        """
        return [col for col in wf.data.columns if col.endswith("_QC")]

    def get_std_variables(self, wf):
        """
        returns a list of standard deviation variables within a waterframe
        """
        return [col for col in wf.data.columns if col.endswith("_STD")]

    def load_csv_data(self, filename, sep=",") -> (pd.DataFrame, list):
        """
        Loads data from a CSV file
        """
        header_lines = csv_detect_header(filename)
        df = pd.read_csv(filename, skiprows=header_lines, sep=sep)
        df = self.harmonize_dataframe(df)
        return df

    def harmonize_dataframe(self, df):
        """
        Takes a dataframe and harmonizes all variable names. All vars are converter to upper case except for lat, lon
        and depth.All QC and STD vars are put to uppercase.
        """
        # harmonize time
        for time_key in ["time", "timestamp", "datetime", "date time"]:
            for key in df.columns:
                if key.lower() == time_key:
                   df = df.rename(columns={key: "time"})

        for var in df.columns:
            skip = False
            for dim in self.__dimensions:  # skip all dimensions and QC related to dimensions
                if var.startswith(dim):
                    skip = True
            if not skip:
                df = df.rename(columns={var: var.upper()})

        # make sure that _QC are uppercase
        for var in df.columns:
            if var.lower().endswith("_qc"):
                df = df.rename(columns={var: var[:-3] + "_QC"})

        # make sure that _QC are uppercase
        for var in df.columns:
            if var.lower().endswith("_std"):
                df = df.rename(columns={var: var[:-4] + "_STD"})

        missing_data = qc_flags["missing_value"]
        for col in df.columns:
            # make sure no NaNs are present in the dataframe
            if col.endswith("_QC"):
                if df[col].dtype != int:
                    df[col] = df[col].replace(np.nan, missing_data)  # instead of nan put missing value
                    df[col] = df[col].astype(int)

            # replace NaN by fill value
            else:
                if df[col].isnull().any():
                    df[col] = df[col].replace(np.nan, self.__fill_value)

        return df

    def load_metadata(self, files: list):
        """
        Loads metadata from files and assigns it to the waterframes
        :param files: metadata files arranged in a list
        """

        if len(files) != len(self.data):
            raise ValueError("Number of data and metadata files do not match!")

        for i in range(len(self.data)):
            wf = self.data[i]
            filename = files[i]

            with open(filename) as f:
                metadata = json.load(f)

            metadata = self.autofill(metadata, wf)  # fill derived attributes
            if metadata["global"]:
                wf.metadata = merge_dicts(metadata["global"], wf.metadata)

            for varname, varmeta in metadata["variables"].items():
                rich.print(f"Loading metadata from variable {varname}...", end="")
                wf.vocabulary[varname] = merge_dicts(varmeta, wf.vocabulary[varname])
                rich.print("[green]done!")

            wf.metadata["$metadatafile"] = filename

            self.data[i] = wf

    def propagate_sensor_metadata(self, metadata):
        """
        Takes a metadata dict and propagates the file-wide sensor information to all the variables
        """
        if not "sensor" in metadata.keys():
            return metadata  # no file-wide sensor info

        sensor_meta = metadata["sensor"]
        for varname, varmeta in metadata["variables"].items():
            # Propagate only in variables, not dimensions, QCs or STDs
            if varname not in self.__dimensions and not varname.endswith("_QC") and not varname.endswith("_STD"):
                varmeta = merge_dicts(sensor_meta, varmeta)
                metadata["variables"][varname] = varmeta

        del metadata["sensor"]

        return metadata

    def autofill(self, metadata: dict, wf: md.WaterFrame) -> dict:
        """
        Tries to fill the missing metadata fields with existing and default information
        :param metadata: dict with the metadata
        :param wf: WaterFrame containing the data and metadata
        :returns: filled metadata
        """
        check_mandatory_fields(metadata["global"])
        check_mandatory_fields(metadata["sensor"])
        [check_mandatory_fields(metadata["variables"][v]) for v in metadata["variables"].keys()]

        metadata["variables"] = self.autofill_variables(metadata["variables"])
        metadata["variables"] = self.autofill_dimensions(metadata["variables"])

        metadata["global"] = self.autofill_global(metadata["global"])
        metadata["sensor"] = self.autofill_sensor(metadata["sensor"])

        # Propagate from global sensor metadata to every variable
        metadata = self.propagate_sensor_metadata(metadata)

        metadata["variables"] = self.autofill_qc(metadata["variables"])
        metadata["variables"] = self.autofill_std(metadata["variables"], wf)

        metadata["variables"] = self.autofill_ancillary(metadata["variables"], wf)

        # Reorder variable metadata
        new_order = ["time", "depth", "depth_QC", "latitude", "latitude_QC", "longitude", "longitude_QC"]
        new = {}
        rich.print(metadata["variables"])
        for o in new_order:
            new[o] = metadata["variables"].pop(o)
        new.update(metadata["variables"])
        metadata["variables"] = new
        rich.print(metadata["variables"])

        return metadata

    def autofill_variables(self, variables: dict) -> dict:
        """
        Fills variable metadata
        """
        data = {}
        for varname, v in variables.items():
            v = process_metadata(v)
            sdn_parameter_uri = self.emso.harmonize_uri(v["sdn_parameter_uri"])
            rich.print("propagating from P01 URI...")
            label = self.emso.vocab_get("P01", sdn_parameter_uri, "prefLabel")
            sdn_id = self.emso.vocab_get("P01", sdn_parameter_uri, "id")
            v["sdn_parameter_urn"] = sdn_id
            v["sdn_parameter_name"] = label.strip()

            if v["sdn_uom_uri"]:
                sdn_uom_uri = v["sdn_uom_uri"]
            else:
                rich.print(f"[yellow]WARNING: units not set, using P01 default units...")
                sdn_uom_uri = self.emso.get_relation("P01", sdn_parameter_uri, "related", "P06")

            label = self.emso.vocab_get("P06", sdn_uom_uri, "prefLabel")
            iden = self.emso.vocab_get("P06", sdn_uom_uri, "id")
            v["sdn_uom_uri"] = sdn_uom_uri
            v["sdn_uom_urn"] = iden
            v["sdn_uom_name"] = label.strip()
            v["units"] = label
            try:
                standard_name_uri = self.emso.get_relation("P01", sdn_parameter_uri, "broader", "P07")
            except LookupError:
                p02_uri = self.emso.get_relation("P01", sdn_parameter_uri, "broader", "P02")
                standard_name_uri = self.emso.get_relation("P02", p02_uri, "narrower", "P07")
            v["standard_name"] = self.emso.vocab_get("P07", standard_name_uri, "prefLabel")
            data[varname] = v
        return data

    def autofill_global(self, m: dict) -> dict:
        m = process_metadata(m)
        if "Conventions" not in m.keys():
            m["Conventions"] = ["EMSO ERIC", "OceanSITES"]

        # Getting EDMO URL from the code
        edmo_code = m["institution_edmo_code"]
        m = set_default_value(m, "insitution_emdo_uri", f"https://edmo.seadatanet.org/report/{edmo_code}")
        m = set_default_value(m, "update_interval", f"void")
        m = set_default_value(m, "Conventions", ["EMSO", "OceanSITES"])
        m = set_default_value(m, "format_version", "0.1")
        m = set_default_value(m, "network", "EMSO ERIC")
        m = set_default_value(m, "data_mode", "EMSO ERIC")
        m = set_default_value(m, "license", "CC-BY-4.0")

        m["license_uri"] = self.emso.spdx_license_uris[m["license"]]
        rich.print(f"licsense uri: {m['license_uri']}")
        return m

    def autofill_sensor(self, s: dict) -> dict:
        s = process_metadata(s)
        sensor_uri = s["sensor_model_uri"]
        rich.print("Propagating sensor model info...", sensor_uri)
        s["sensor_model_name"] = self.emso.vocab_get("L22", sensor_uri, "prefLabel")
        s["sensor_model_urn"] = self.emso.vocab_get("L22", sensor_uri, "id")
        manufacturer_uri = self.emso.get_relation("L22", sensor_uri, "related", "L35")
        s["sensor_manufacturer_uri"] = manufacturer_uri
        s["sensor_manufacturer_urn"] = self.emso.vocab_get("L35", manufacturer_uri, "id")
        s["sensor_manufacturer_name"] = self.emso.vocab_get("L35", manufacturer_uri, "prefLabel")
        return s

    def autofill_dimensions(self, variables: dict) -> dict:
        """
        Fills metadata for the dimensions
        """
        for dname in self.__dimensions:
            if dname not in variables:
                dmeta = dimension_metadata(dname)
            elif not variables[dname]:
                dmeta = dimension_metadata(dname)
            else:
                dmeta = variables[dname]

            sdn_parameter_uri = self.emso.harmonize_uri(dmeta["sdn_parameter_uri"])
            label = self.emso.vocab_get("P01", sdn_parameter_uri, "prefLabel")
            sdn_id = self.emso.vocab_get("P01", sdn_parameter_uri, "id")
            dmeta["sdn_parameter_urn"] = sdn_id
            dmeta["sdn_parameter_name"] = label.strip()

            if "sdn_uom_uri" in dmeta.keys() and dmeta["sdn_uom_uri"]:
                sdn_uom_uri = dmeta["sdn_uom_uri"]
            else:
                rich.print(f"[yellow]WARNING: units not set, using P01 default units...")
                sdn_uom_uri = self.emso.get_relation("P01", sdn_parameter_uri, "related", "P06")

            label = self.emso.vocab_get("P06", sdn_uom_uri, "prefLabel")
            iden = self.emso.vocab_get("P06", sdn_uom_uri, "id")
            dmeta["sdn_uom_uri"] = sdn_uom_uri
            dmeta["sdn_uom_urn"] = iden
            dmeta["sdn_uom_name"] = label.strip()
            dmeta["units"] = label
            if "standard_name" not in dmeta.keys() or not dmeta["standard_name"]:
                try:
                    standard_name_uri = self.emso.get_relation("P01", sdn_parameter_uri, "broader", "P07")
                except LookupError:
                    p02_uri = self.emso.get_relation("P01", sdn_parameter_uri, "broader", "P02")
                    standard_name_uri = self.emso.get_relation("P02", p02_uri, "narrower", "P07")
                dmeta["standard_name"] = self.emso.vocab_get("P07", standard_name_uri, "prefLabel")
            variables[dname] = dmeta
        return variables

    def autofill_qc(self, m):
        """
        If not present, generate quality control metadata, compliant with oceansites format
        """
        # Get variable list, ignoring quality control (_QC) and standard deviation columns (_STD)

        variables = [v for v in m.keys() if not v.endswith("_QC") and not v.endswith("_STD")]

        for varname in variables:
            if varname == "time":
                continue  # skip time

            qc_varname = varname + "_QC"
            if qc_varname not in m.keys():
                m[qc_varname] = {}
            long_name = m[varname]["long_name"]
            d = quality_control_metadata(long_name)
            m[qc_varname] = merge_dicts(m[qc_varname], d)
        return m

    def autofill_std(self, m: dict, wf: md.WaterFrame):
        """
        If not present, generate standard deviation, compliant with oceansites format
        """
        # Get variable list, ignoring quality control (_QC) and standard deviation columns (_STD)
        std_variables = [v for v in wf.data.columns if v.endswith("_STD")]

        for std_varname in std_variables:
            varname = std_varname.replace("_STD", "")
            long_name = m[varname]["long_name"]
            d = {
                "long_name": long_name + " standard deviation",
                "comment": f"standard deviation associated to each {varname} mean value",
                "units": m[varname]["units"]
            }
            if std_varname not in m.keys():
                m[std_varname] = {}
            m[std_varname] = merge_dicts(m[std_varname], d)
        return m

    def autofill_ancillary(self, variables, wf):
        """
        Creates anciallary_variables
        """
        qc_variables = self.get_qc_variables(wf)
        std_variables = self.get_std_variables(wf)
        for varname, varmeta in variables.items():
            if varname in qc_variables or varname in std_variables:
               continue

            rich.print(f"Processing [purple]{varname}")
            ancillary = []
            [ancillary.append(a) for a in qc_variables if varname + "_QC" == a]   # Append QCs
            [ancillary.append(a) for a in std_variables if varname + "_STD" == a] # Append STDs

            if ancillary:
                varmeta["ancillary_variables"] = ancillary
        return variables

    def set_coordinate(self, key, values):
        """
        Set a coordinate in every dataframe. Add a QC column with nominal_value flag
        """
        if not values:
            rich.print("[yellos]WARNING: No values to be set!!")
            return None

        if len(values) != 1 and len(values) != len(self.data):
            raise ValueError(f"Got {len(self.data)} data files, but got {len(values)} {key} values, expected one value for "
                             f"all or a value for every data file")

        qc_value = qc_flags["nominal_value"]
        if len(values) == 1:
            # assign the same value to all waterframes
            rich.print(f"Adding fixed {key} for all data files, depth: {values[0]:.02f}")
            values = [values[0] for _ in range(len(self.data))]

        for i in range(len(self.data)):
            wf = self.data[i]
            df = wf.data
            df[key] = values[i]
            df[key + "_QC"] = qc_value
            if key not in wf.vocabulary.keys():
                dmetadata = dimension_metadata(key)  # add empty vocab
                wf.vocabulary[key] = dmetadata
            wf.vocabulary[key + "_QC"] = quality_control_metadata(dmetadata["long_name"])

    def set_coordinates(self, depths: list, latitudes: list, longitudes: list):
        """
        Takes a list of depths/latitudes/longitudes and sets it as a column in the dataframes
        """
        self.set_coordinate("depth", depths)
        self.set_coordinate("latitude", latitudes)
        self.set_coordinate("longitude", longitudes)

    def ensure_coordinates(self, required=["depth", "latitude", "longitude"]):
        """
        Make sure that depth, lat and lon variables (and their QC) are properly set
        """
        error = False
        for wf in self.data:
            df = wf.data
            for r in required:
                if r not in df.columns:
                    error = True
                    rich.print(f"[red]Coordinate {r} is missing!")

        if error:
            raise ValueError("Coordinates not properly set")

    def merge_data(self):
        """
        Combine all WaterFrames into a single waterframe. Both data and metadata are consolidated into a single
        structure
        """
        self.ensure_coordinates()
        dataframes = []  # list of dataframes
        global_attr = []   # list of dict containing global attributes
        variables_attr = {}   # dict all the variables metadata
        i = 0
        for wf in self.data:
            df = wf.data
            # setting time as the index
            df["time"] = pd.to_datetime(df["time"])
            df = df.set_index("time")
            df = df.sort_index(ascending=True)

            df["sensor_id"] = i
            i += 1
            wf.vocabulary["sensor_id"] = {"description": "serial number of the sensor"}

            dataframes.append(df)
            global_attr.append(wf.metadata)
            for varname, varmeta in wf.vocabulary.items():
                if varname not in variables_attr.keys():
                    variables_attr[varname] = [varmeta]  # list of dicts with metadata
                else:
                    variables_attr[varname].append(varmeta)
        df = pd.concat(dataframes)  # Consolidate data in a single dataframe
        df = df.sort_index(ascending=True)  # sort by date
        df = df.reset_index()  # get back to numerical index

        # Consolidating Global metadata, the position in the array is the priority
        global_meta = {}
        for g in reversed(global_attr):  # loop backwards, last element has lower priority
            global_meta = merge_dicts(g, global_meta)

        variable_meta = {}
        for varname, varmeta in variables_attr.items():
            variable_meta[varname] = consolidate_metadata(varmeta)

        wf = md.WaterFrame()
        wf.data = df
        wf.vocabulary = variable_meta
        wf.metadata = global_meta

        # Remove internal elements in metadata
        [wf.metadata.pop(key) for key in wf.metadata.copy().keys() if key.startswith("$")]

        dimensions = self.__dimensions
        self.check_multisensor(wf.vocabulary)
        if self.multi_sensor:
            rich.print("[purple]This is a multi-sensor dataset!!!")
            dimensions.append("sensor_id")

        self.update_global_metadata(wf)

        return wf, dimensions

    def update_global_metadata(self, wf):
        """
        Updates global metadata in a water frame, like time coverage and geospatial max/min
        """
        wf.metadata["geospatial_lat_min"] = wf.data["latitude"].min()
        wf.metadata["geospatial_lat_max"] = wf.data["latitude"].max()
        wf.metadata["geospatial_lon_min"] = wf.data["longitude"].min()
        wf.metadata["geospatial_lon_max"] = wf.data["longitude"].min()
        wf.metadata["geospatial_vertical_min"] = wf.data["depth"].min()
        wf.metadata["geospatial_vertical_max"] = wf.data["depth"].min()
        wf.metadata["time_coverage_start"] = wf.data["time"].min().strftime("%Y-%m-%dT%H:%M:%SZ")
        wf.metadata["time_coverage_end"] = wf.data["time"].max().strftime("%Y-%m-%dT%H:%M:%SZ")



    def check_multisensor(self, variables):
        """
        Looks through all the variables and checks if data comes from two or more sensors. Sets the multisensor flag
        """
        serial_numbers = []
        for varname, varmeta in variables.items():

            if "sensor_serial_number" not in varmeta.keys():
                continue  # avoid QC and STD vars

            if type(varmeta["sensor_serial_number"]) == str:
                if varmeta["sensor_serial_number"] not in serial_numbers:
                    serial_numbers.append(varmeta["sensor_serial_number"])
            elif type(varmeta["sensor_serial_number"]) == list:
                for serial in varmeta["sensor_serial_number"]:
                    if serial not in serial_numbers:
                        serial_numbers.append(serial)
        if len(serial_numbers) > 1:
            rich.print(f"Multiple sensors found: {serial_numbers}")
            self.multi_sensor = True
        elif len(serial_numbers) == 1:
            rich.print(f"Only one sensors found: {serial_numbers[0]}")
            self.multi_sensor = False
        else:
            raise ValueError("No serial numbers found???")
        return self.multi_sensor

    def generate_metadata_templates(self, folder):
        """
        Generate metadata templates based on the data files
        """
        rich.print(f"Generating metadata template in folder {folder}...")
        os.makedirs(folder, exist_ok=True)
        mfiles = []  # metadata files
        for wf in self.data:
            datafile = wf.metadata["$datafile"]
            variables = r["variables"]
            m = {  # Metadata template
                "README": {
                    "*attr": "Mandatory attributes, must be set",
                    "~attr": "Optional attributes, if not set will be guessed by the script",
                    "$attr": "If not provided, will be requested interactively"
                }
            }
            if not self.glob_attr_processed:  # just add globals in the metadata file generated
                m["global"] = global_metadata()
                self.glob_attr_processed = True

            m["variables"] = {}
            m["sensor"] = sensor_metadata()

            for var in variables:
                m["variables"][var] = variable_metadata()

        # create a filename
            a = os.path.basename(datafile).split(".")
            filename = ".".join(a[:-1]) + ".json"
            filename = os.path.join(folder, filename)

            i = 1
            if os.path.exists(filename):
                a = filename.split(".")
                filename = ".".join(a[:-1]) + f"({i}).json"

                while os.path.isfile(filename):
                    i += 1
                    filename = filename.split("(")[0] + f"({i})" + filename.split(")")[1]

            with open(filename, "w") as f:
                f.write(json.dumps(m, indent=4))

            mfiles.append(filename)
        rich.print(f"[green]Please edit the folowing files and run the generator with the -m option!")
        [rich.print(f"    {f}") for f in mfiles]


def generate_metadata(data_files: list, folder):
    """
    Generate the metadata templates for the input file in the target folder
    """
    dataset = EmsoDataset(data_files)
    # If metadata and generate
    rich.print(f"generate {args.generate} folder")
    os.makedirs(folder, exist_ok=True)
    dataset.generate_metadata_templates(args.generate)


def generate_dataset(data_files, metadata_files: list, depths=[], latitudes=[], longitudes=[]):
    """
    Merge data fiiles and metadata files into a NetCDF dataset according to EMSO specs. If provided, depths, lats and
    longs will be added to the dataset as dimensions.
    """
    dataset = EmsoDataset(data_files)

    if args.depths or args.latitudes or args.longitudes:
        dataset.set_coordinates(depths, latitudes, longitudes)

    dataset.ensure_coordinates()

    if args.metadata:
        dataset.load_metadata(metadata_files)

    return dataset


if __name__ == "__main__":
    argparser = ArgumentParser()
    argparser.add_argument("-v", "--verbose", action="store_true", help="Shows verbose output", default=False)
    argparser.add_argument("-d", "--data", type=str, help="List of data files (CSV or NetCDF)", required=True,
                           nargs="+")
    argparser.add_argument("-m", "--metadata", type=str, help="List of JSON metadata documents", required=False,
                           nargs="+")
    argparser.add_argument("-g", "--generate", type=str, help="Generates metadata templates in the specified folder",
                           required=False)

    # Coordinates
    argparser.add_argument("-D", "--depths", type=float, help="List of nominal depths", required=False, nargs="+")
    argparser.add_argument("-l", "--latitudes", type=float, help="List of nominal latitudes", required=False, nargs="+")
    argparser.add_argument("-L", "--longitudes", type=float, help="List of nominal longitudes", required=False,
                           nargs="+")

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

    dataset = generate_dataset(args.data, args.metadata, depths=args.depths, latitudes=args.latitudes, longitudes=args.longitudes)

    wf, dims = dataset.merge_data()
    # dims = ["latitude", "longitude", "depth", "sensor_id", "time"]
    to_multidim_nc(wf, "out.nc", dimensions=dims, fill_value=-999, time_key="time")
