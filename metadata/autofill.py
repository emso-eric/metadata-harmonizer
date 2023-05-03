#!/usr/bin/env python3
"""
Functions to autofill missing metadata

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 29/4/23
"""

from argparse import ArgumentParser
import json
import mooda as md
import rich
from metadata import EmsoMetadata
from metadata.constants import dimensions, iso_time_format
from metadata.metadata_templates import choose_interactively, dimension_metadata, quality_control_metadata
from metadata.utils import merge_dicts


def autofill(wf: md.WaterFrame, minmeta: dict):
    pass


def set_default(m: dict, key: str, value: any):
    """
    Sets the key:value if key doesn't exist or current value is null
    """
    if key not in m.keys():
        m[key] = value
    elif not m[key]:
        m[key] = value
    return m


def autofill_minmeta(minmeta: dict, emso: EmsoMetadata):
    """
    Takes a minimal metadata JSON dict and tries to fill the gaps with default values
    """
    rich.print("autofilling global metatadata...", end="")
    set_default(minmeta["global"], "~Conventions", ["OceanSITES", "EMSO"])
    set_default(minmeta["global"], "~format_version", "1.4")
    set_default(minmeta["global"], "~update_interval", "void")
    set_default(minmeta["global"], "~network", "EMSO")
    set_default(minmeta["global"], "~license", "CC-BY-4.0")
    rich.print("[green]done!")
    for varname, varmeta in minmeta["variables"].items():
        rich.print(f"   processing variable [cyan]{varname}[/cyan]...", end="")
        sdn_parameter_uri = emso.harmonize_uri(varmeta["*sdn_parameter_uri"])
        sdn_uom_uri = emso.get_relation("P01", sdn_parameter_uri, "related", "P06")
        set_default(varmeta, "~sdn_uom_uri", sdn_uom_uri)

        if "~standard_name" not in varmeta.keys() or not varmeta["~standard_name"]:
            standard_name_uris = emso.get_relations("P01", sdn_parameter_uri, "broader", "P07")
            if len(standard_name_uris) == 1:
                standard_name_uri = standard_name_uris[0]  # Match!
                standard_name = emso.vocab_get("P07", standard_name_uri, "prefLabel")
            elif len(standard_name_uris) > 1:
                standard_names = [emso.vocab_get("P07", s, "prefLabel") for s in standard_name_uris]
                # Let the user choose interactively which one
                standard_name = choose_interactively("standard_name", "", standard_names)
            else:
                # No P07 links found for this URI, so instead of P01 try to use the broader P02
                p02_uri = emso.get_relation("P01", sdn_parameter_uri, "broader", "P02")
                standard_name_uris = emso.get_relations("P02", p02_uri, "narrower", "P07")
                if len(standard_name_uris) == 1:
                    standard_name_uri = standard_name_uris[0]  # Match!
                    standard_name = emso.vocab_get("P07", standard_name_uri, "prefLabel")
                elif len(standard_name_uris) > 1:
                    standard_names = [emso.vocab_get("P07", s, "prefLabel") for s in standard_name_uris]
                    # Let the user choose interactively which one
                    standard_name = choose_interactively("standard_name", varname, standard_names)
                else:
                    rich.print("[red]Could not deduce any standard_name!")
                    standard_name = ""
            set_default(varmeta, "~standard_name", standard_name)

        rich.print("[green]done!")
    return minmeta


def expand_minmeta(wf: md.WaterFrame, minmeta: dict, emso: EmsoMetadata) -> dict:
    """
    Expands minimal metadata into full metadata and sotres it within the WaterFrame
    """
    rich.print("Expanding minimal metadata into full metadata document:")
    metadata = minmeta.copy()

    if "coordinates" in metadata.keys():
        del metadata["coordinates"]

    metadata["global"] = autofill_global(metadata["global"], emso)
    metadata["sensor"] = autofill_sensor(metadata["sensor"], emso)

    # Propagate from global sensor metadata to every variable
    metadata, sensor_id = propagate_sensor_metadata(metadata)
    wf.metadata["$sensor_id"] = sensor_id

    # Now, add dimensions info
    for dimname in dimensions:
        rich.print(f"    adding metadata for dimension [purple]{dimname}[/purple]...", end="")
        metadata["variables"][dimname] = dimension_metadata(dimname)
        rich.print("[green]done")

    # Autofill all variables
    [autofill_variable(v, emso) for name, v in metadata["variables"].items() if name != "sensor_id"]

    # Add QC metadata for all variables and dimensions
    for varname, varmeta in metadata["variables"].copy().items():
        if varname == "sensor_id":
            continue
        rich.print(f"    adding metadata for variable  [cyan]{varname + '_QC'}[/cyan]...", end="")
        qcmeta = quality_control_metadata(varmeta["long_name"])
        metadata["variables"][varname + "_QC"] = qcmeta
        rich.print("[green]done")

    full_meta_file = wf.metadata["$minmeta"].replace(".min.json", ".full.json")

    rich.print(f"Storing full metadata into {full_meta_file}...", end="")
    with open(full_meta_file, "w") as f:
        f.write(json.dumps(metadata, indent=2))
    rich.print("[green]done!")

    rich.print("[green]Full metadata created!\n")
    return metadata


def autofill_variable(varmeta: dict, emso: EmsoMetadata) -> dict:
    """
    Expands the variable metadata adding uris, uoms and names for variables and units
    """
    sdn_parameter_uri = emso.harmonize_uri(varmeta["sdn_parameter_uri"])
    label = emso.vocab_get("P01", sdn_parameter_uri, "prefLabel")
    sdn_id = emso.vocab_get("P01", sdn_parameter_uri, "id")
    varmeta["sdn_parameter_urn"] = sdn_id
    varmeta["sdn_parameter_name"] = label.strip()

    if varmeta["sdn_uom_uri"]:
        sdn_uom_uri = varmeta["sdn_uom_uri"]
    else:
        rich.print(f"[yellow]WARNING: units for {sdn_parameter_uri} not set, using P01 default units...")
        sdn_uom_uri = emso.get_relation("P01", sdn_parameter_uri, "related", "P06")

    label = emso.vocab_get("P06", sdn_uom_uri, "prefLabel")
    iden = emso.vocab_get("P06", sdn_uom_uri, "id")
    varmeta["sdn_uom_uri"] = sdn_uom_uri
    varmeta["sdn_uom_urn"] = iden
    varmeta["sdn_uom_name"] = label.strip()
    varmeta["units"] = label
    return varmeta


def autofill_global(m: dict, emso: EmsoMetadata) -> dict:
    if "Conventions" not in m.keys():
        m["Conventions"] = ["EMSO ERIC", "OceanSITES"]

    # Getting EDMO URL from the code
    edmo_code = m["institution_edmo_code"]
    edmo_uri = f"https://edmo.seadatanet.org/report/{edmo_code}"
    m = set_default(m, "institution_edmo_code", edmo_code)
    df = emso.edmo_codes
    institution_name = df.loc[df["uri"] == edmo_uri]["name"].values[0]
    m = set_default(m, "institution_edmo_uri", f"https://edmo.seadatanet.org/report/{edmo_code}")
    m = set_default(m, "institution", institution_name)
    m["license_uri"] = emso.spdx_license_uris[m["license"]]
    return m


def autofill_sensor(s: dict, emso: EmsoMetadata) -> dict:
    sensor_uri = s["sensor_model_uri"]
    rich.print("    propagating sensor model info...", end="")
    try:
        s["sensor_model"] = emso.vocab_get("L22", sensor_uri, "prefLabel")
        s["sensor_SeaVoX_L22_code"] = emso.vocab_get("L22", sensor_uri, "id")
    except LookupError:
        rich.print("[red]model not found in L22!")
        s["sensor_SeaVoX_L22_code"] = ""
        s["sensor_manufacturer_uri"] = ""
        s["sensor_manufacturer_urn"] = ""
        s["sensor_manufacturer_name"] = ""
        return s

    try:
        manufacturer_uri = emso.get_relation("L22", sensor_uri, "related", "L35")
        s["sensor_manufacturer_uri"] = manufacturer_uri
        s["sensor_manufacturer_urn"] = emso.vocab_get("L35", manufacturer_uri, "id")
        s["sensor_manufacturer_name"] = emso.vocab_get("L35", manufacturer_uri, "prefLabel")
    except LookupError:
        rich.print("[red]No manufacturer found on SeaDataNet L35 vocab!!")
        s["sensor_manufacturer_uri"] = ""
        s["sensor_manufacturer_urn"] = ""
        s["sensor_manufacturer_name"] = ""
    return s


def autofill_waterframe_coverage(wf: md.WaterFrame) -> md.WaterFrame:
    """
    Autofills geospatial and time coverage in a WaterFrame
    """
    wf.metadata["geospatial_lat_min"] = wf.data["latitude"].min()
    wf.metadata["geospatial_lat_max"] = wf.data["latitude"].max()
    wf.metadata["geospatial_lon_min"] = wf.data["longitude"].min()
    wf.metadata["geospatial_lon_max"] = wf.data["longitude"].min()
    wf.metadata["geospatial_vertical_min"] = int(wf.data["depth"].min())
    wf.metadata["geospatial_vertical_max"] = int(wf.data["depth"].min())
    wf.metadata["time_coverage_start"] = wf.data["time"].min().strftime(iso_time_format)
    wf.metadata["time_coverage_end"] = wf.data["time"].max().strftime(iso_time_format)
    return wf


def propagate_sensor_metadata(metadata: dict) -> (dict, str):
    """
    Takes a metadata dict and propagates the file-wide sensor information to all the variables
    """
    if not "sensor" in metadata.keys():
        return metadata  # no file-wide sensor info

    sensor_meta = metadata["sensor"]
    for varname, varmeta in metadata["variables"].items():
        # Propagate only in variables, not dimensions, QCs or STDs
        if varname not in dimensions and not varname.endswith("_QC") and not varname.endswith("_STD"):
            varmeta = merge_dicts(sensor_meta, varmeta)
            metadata["variables"][varname] = varmeta

    sensor_id = metadata["sensor"]["sensor_serial_number"]
    del metadata["sensor"]
    return metadata, sensor_id
