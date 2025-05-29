#!/usr/bin/env python3
"""
This class implements tools to generate and manage minimal metadata templates. Minimal metadata templates is the
minimum set of info required to generate a dataset.

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 29/4/23
"""
import logging

from . import EmsoMetadata
from .autofill import autofill_minmeta, expand_minmeta
from .metadata_templates import global_metadata, sensor_metadata, variable_metadata, user_selectable_attributes, \
    choose_interactively, platform_metadata
import rich
import os
from .dataset import extract_netcdf_metadata
import json
import numpy as np

from .utils import avoid_filename_collision
from .waterframe import WaterFrame

def generate_min_meta_template(wf: WaterFrame, folder: str):
    """
    Takes a data frame and generates a minimal metadata file from which the rest of the metadata can be derived
    """
    os.makedirs(folder, exist_ok=True)
    mfiles = []  # metadata files

    variables = [varname for varname in wf.vocabulary.keys() if not varname.endswith("_QC")]
    m = {
        "README": {
            "*attr": "Mandatory attributes, must be set",
            "~attr": "Optional attributes, if not set will be guessed by the script",
            "$attr": "If not provided, will be requested interactively"
        },
        "global": global_metadata(),
        "variables": {},
        "sensor": sensor_metadata(),
        "platform": platform_metadata()
    }

    for var in variables:
        m["variables"][var] = variable_metadata()

    datafile = wf.metadata["$datafile"]
    # create a filename
    a = os.path.basename(datafile).split(".")
    filename = ".".join(a[:-1]) + ".min.json"
    filename = os.path.join(folder, filename)

    # Do not overwrite file.txt, but create file(1).txt

    if os.path.exists(filename):
        filename = avoid_filename_collision(filename)

    with open(filename, "w") as f:
        f.write(json.dumps(m, indent=2))

    mfiles.append(filename)
    [rich.print(f"    {f}") for f in mfiles]


def process_selectable_metadata(m, filename=""):
    """
    Asks the user to interactively choose missing parameters
    """
    # Processing interactive values
    for key, value in m.copy().items():
        if key.startswith("$"):
            k = key[1:]
            if not value:
                if filename:
                    value = choose_interactively(k, filename, user_selectable_attributes()[k])
                else:
                    raise ValueError("Can't ask interactively for data if no filename is passed")
            m[key] = value  # remove leading $ and add user selected value
    return m


def remove_minmeta_keys(m):
    """
    Removes the minmeta leading keys (* ~ $)
    """
    # Process the rest of the params...
    for key, value in m.copy().items():
        if key.startswith("~") or key.startswith("*") or key.startswith("$"):
            del m[key]
            m[key[1:]] = value  # remove leading *

    if "README" in m.keys():
        del m["README"]
    return m


def load_metadata(filename: str,  emso: EmsoMetadata) -> dict:
    """
    Loads metadata. Filename can be a min meta document (*.min.json) or a full metadata doc (*.full.json)
    """
    if filename.endswith(".min.json"):
        metadata = load_min_meta(filename, emso)
        metadata = expand_minmeta(metadata, emso, filename)
    elif filename.endswith(".full.json"):
        metadata = load_full_meta(filename)
    else:
        raise ValueError("Filename must be a minimal metadata file (.min.json) or full metadata file (.full.json)")
    return metadata


def load_full_meta(filename: str) -> dict:
    """
    Loads a full metadata file and return it as a dictionary
    """
    log = logging.getLogger("emh")
    log.info(f"Loading full metadata from {filename}")
    with open(filename) as f:
        metadata = json.load(f)
    return metadata


def load_min_meta(filename: str, emso: EmsoMetadata) -> dict:
    """
    Loads a minimal metadata file.
    """
    log = logging.getLogger("emh")
    log.info(f"Loading minimal metadata from {filename}")
    with open(filename) as f:
        metadata = json.load(f)

    metadata["global"] = process_selectable_metadata(metadata["global"], filename=filename)
    check_mandatory_fields(metadata["global"])

    for i, sensor in enumerate(metadata["sensors"]):
        metadata["sensors"][i] = process_selectable_metadata(sensor, filename=filename)
        check_mandatory_fields(sensor)

    for i, platform in enumerate(metadata["platforms"]):
        metadata["platforms"][i] = process_selectable_metadata(platform, filename=filename)
        check_mandatory_fields(platform)

    for var, m in metadata["variables"].items():
        metadata["variables"][var] = process_selectable_metadata(m, filename=filename)

    # Make sure that we have all the necessary info
    for var, m in metadata["variables"].items():
        check_mandatory_fields(m)

    metadata = metadata.copy()
    metadata = autofill_minmeta(metadata, emso)

    if filename:
        rich.print(f"Updating file {filename} with selected user choices...", end="")
        with open(filename, "w") as f:
            f.write(json.dumps(metadata, indent=2))  # update the file, so
        rich.print("[green]done!")

    # Remove the leading keys
    metadata["global"] = remove_minmeta_keys(metadata["global"])

    for i, sensor in enumerate(metadata["sensors"]):
        metadata["sensors"][i] = remove_minmeta_keys(sensor)

    for i, platform in enumerate(metadata["platforms"]):
        metadata["platforms"][i] = remove_minmeta_keys(platform)

    for var, m in metadata["variables"].items():
        metadata["variables"][var] = remove_minmeta_keys(m)

    if "README" in metadata.keys():
        del metadata["README"]
    return metadata


def check_mandatory_fields(m):
    """
    Checks that all fields starting with * are filled
    """
    m = m.copy()
    error = False

    # First check all mandatory fields
    for key, value in m.copy().items():
        if key.startswith("*") and not value:
            error = True
            rich.print(f"[red]Mandatory field missing: \"{key}\"")
        if error:
            raise SyntaxError("Missing fields detected! Please fill all fields starting with '*'")

def np_encoder(object):
    """
    Encodes Numpy data for JSON lib
    """
    if isinstance(object, np.generic):
        return object.item()

def generate_full_metadata(wf: WaterFrame, folder):
    """
    Takes a waterframe and stores its full metadtaa in to a JSON file
    """

    os.makedirs(folder, exist_ok=True)
    # metadata file will be the datafile with full.json extension
    metafile = ".".join(wf.metadata["$datafile"].split(".")[:-1]) + ".full.json"
    metafile = os.path.join(folder, metafile)
    wf.metadata["$fullmeta"] = metafile
    rich.print(f"Storing full metadata into {metafile}...", end="")
    metadata = extract_netcdf_metadata(wf)
    with open(metafile, "w") as f:
        f.write(json.dumps(metadata, indent=2, default=np_encoder))
    rich.print("[green]done!")

