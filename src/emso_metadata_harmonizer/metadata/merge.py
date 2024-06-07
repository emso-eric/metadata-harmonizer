import pandas as pd
import rich

from .autofill import autofill_waterframe_coverage
from .constants import iso_time_format
from .dataset import consolidate_metadata, set_multisensor
from .utils import merge_dicts
from .waterframe import WaterFrame


def merge_waterframes(waterframes):
    """
    Combine all WaterFrames into a single waterframe. Both data and metadata are consolidated into a single
    structure
    """
    dataframes = []  # list of dataframes
    global_attr = []  # list of dict containing global attributes
    variables_attr = {}  # dict all the variables metadata
    for wf in waterframes:
        df = wf.data
        # setting time as the index
        df = df.set_index("TIME")
        df = df.drop_duplicates(keep="first")
        df = df.sort_index(ascending=True)
        df["SENSOR_ID"] = wf.metadata["$sensor_id"]

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

    wf = WaterFrame(df, global_meta, variable_meta)

    try:
        wf = set_multisensor(wf)
    except LookupError as e:
        rich.print(f"[red]ERROR {e}")

    wf = autofill_waterframe_coverage(wf)  # update the coordinates max/min in metadata

    # Add versioning info
    now = pd.Timestamp.now(tz="utc").strftime(iso_time_format)
    if len(waterframes) > 1:
        # New waterframe
        wf.metadata["date_created"] = now
        wf.metadata["date_modified"] = now
    else:  # just update the date_modified
        if "date_created" not in wf.metadata.keys():
            wf.metadata["date_created"] = now
        wf.metadata["date_modified"] = wf.metadata["date_created"]
    return wf
