#!/usr/bin/env python3
"""
Miscellaneous functions

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 26/4/23
"""

import mooda as md
import rich
from rich.progress import Progress
import urllib
import concurrent.futures as futures
import os
from metadata.constants import dimensions


def get_netcdf_metadata(filename):
    """
    Returns the metadata from a NetCDF file
    :param: filename
    :returns: dict with the metadata { "global": ..., "variables": {"VAR1": {...},"VAR2":{...}}
    """
    wf = md.read_nc(filename)
    metadata = {
        "global": wf.metadata,
        "variables": wf.vocabulary
    }
    return group_metadata_variables(metadata)


def group_metadata_variables(metadata):
    """
    Takes a dictionary with all the variables in the "variable" and groups them into "variables", "qualityControl" and
    "dimensions"
    """

    m = metadata.copy()

    rich.print(m)

    vars = list(m["variables"].keys())

    qcs = {key: m["variables"].pop(key) for key in vars if key.upper().endswith("_QC")}
    stds = {key: m["variables"].pop(key) for key in vars if key.upper().endswith("_STD")}
    dims = {key: m["variables"].pop(key) for key in vars if key in dimensions}

    m = {
        "global": m["global"],
        "variables": m["variables"],
        "qc": qcs,
        "dimensions": dims,
        "std": stds
    }
    rich.print(m)
    return m


def __threadify_index_handler(index, handler, args):
    """
    This function adds the index to the return of the handler function. Useful to sort the results of a
    multi-threaded operation
    :param index: index to be returned
    :param handler: function handler to be called
    :param args: list with arguments of the function handler
    :return: tuple with (index, xxx) where xxx is whatever the handler function returned
    """
    result = handler(*args)  # call the handler
    return index, result  # add index to the result


def threadify(arg_list, handler, max_threads=10, text: str = "progress..."):
    """
    Splits a repetitive task into several threads
    :param arg_list: each element in the list will crate a thread and its contents passed to the handler
    :param handler: function to be invoked by every thread
    :param max_threads: Max threads to be launched at once
    :return: a list with the results (ordered as arg_list)
    """
    index = 0  # thread index
    with futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        threads = []  # empty thread list
        results = []  # empty list of thread results
        for args in arg_list:
            # submit tasks to the executor and append the tasks to the thread list
            threads.append(executor.submit(__threadify_index_handler, index, handler, args))
            index += 1

        # wait for all threads to end
        with Progress() as progress:  # Use Progress() to show a nice progress bar
            task = progress.add_task(text, total=index)
            for future in futures.as_completed(threads):
                future_result = future.result()  # result of the handler
                results.append(future_result)
                progress.update(task, advance=1)

        # sort the results by the index added by __threadify_index_handler
        sorted_results = sorted(results, key=lambda a: a[0])

        final_results = []  # create a new array without indexes
        for result in sorted_results:
            final_results.append(result[1])
        return final_results


def download_files(tasks, force_download=False):
    if len(tasks) == 1:
        return None
    rich.print("Downloading files...")
    args = []
    for url, file, name in tasks:
        if os.path.isfile(file) and not force_download:
            rich.print(f"    [dark_grey]{name} already downloaded")
        else:
            rich.print(f"    downloading [cyan]'{name}'[/cyan]...")
            args.append((url, file))

    threadify(args, urllib.request.urlretrieve)
