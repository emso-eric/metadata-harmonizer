#!/usr/bin/env python3
"""
Miscellaneous functions

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 26/4/23
"""
import rich
from rich.progress import Progress
import urllib
import concurrent.futures as futures
import os
from .constants import dimensions
import numpy as np


def group_metadata_variables(metadata):
    """
    Takes a dictionary with all the variables in the "variable" and groups them into "variables", "qualityControl" and
    "dimensions"
    """

    m = metadata.copy()

    vars = list(m["variables"].keys())

    qcs = {key: m["variables"].pop(key) for key in vars if key.upper().endswith("_QC")}
    stds = {key: m["variables"].pop(key) for key in vars if key.upper().endswith("_STD")}
    dims = {key: m["variables"].pop(key) for key in vars if key.upper() in dimensions}

    technical = {}
    for key in vars:
        try:
            if "technical_data" in m["variables"][key].keys():
                rich.print(f"variable {key} is 'technical'")
                technical[key] = m["variables"].pop(key)
        except KeyError:
            rich.print(f"variable {key} is 'scientific'")

    m = {
        "global": m["global"],
        "variables": m["variables"],
        "qc": qcs,
        "dimensions": dims,
        "std": stds,
        "technical": technical
    }
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


def threadify(arg_list, handler, max_threads=10):
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
        for future in futures.as_completed(threads):
            future_result = future.result()  # result of the handler
            results.append(future_result)

        # sort the results by the index added by __threadify_index_handler
        sorted_results = sorted(results, key=lambda a: a[0])

        final_results = []  # create a new array without indexes
        for result in sorted_results:
            final_results.append(result[1])
        return final_results


def download_file(url, file):
    """
    wrapper for urllib.error.HTTPError
    """
    try:
        return urllib.request.urlretrieve(url, file)
    except urllib.error.HTTPError as e:
        rich.print(f"[red]{str(e)}")
        rich.print(f"[red]Could not download from {url} to file {file}")
        raise e


def download_files(tasks, force_download=False):
    if len(tasks) == 1:
        return None
    args = []
    for url, file, name in tasks:
        if os.path.isfile(file) and not force_download:
            pass
        else:
            args.append((url, file))

    threadify(args, download_file)


def drop_duplicates(df, timestamp="time"):
    """
    useful for datasets that have duplicated values with consecutive timestamps (e.g. data is generated minutely, but
    inserted into a database every 20 secs). So the following dataframe:

                                col1      col2    col3
        timestamp
        2020-01-01 00:00:00    13.45    475.45    12.7
        2020-01-01 00:00:00    13.45    475.45    12.7
        2020-01-01 00:00:00    13.45    475.45    12.7
        2020-01-01 00:01:00    12.89    324.12    78.8
        2020-01-01 00:01:00    12.89    324.12    78.8
        2020-01-01 00:01:00    12.89    324.12    78.8
        ...

    will be simplified to:

                                col1      col2    col3
        timestamp
        2020-01-01 00:00:00    13.45    475.45    12.7
        2020-01-01 00:01:00    12.89    324.12    78.8

    :param df: input dataframe
    :return: simplified dataframe
    """
    if df.empty:
        rich.print("[yellow]WARNING empty dataframe")
        return df
    columns = [col for col in df.columns if col != timestamp]
    del_array = np.zeros(len(df))  # create an empty array
    duplicates = 0
    with Progress() as progress:  # Use Progress() to show a nice progress bar
        task = progress.add_task("Detecting duplicates", total=len(df))
        init = True
        for index, row in df.iterrows():
            progress.update(task, advance=1)
            if init:
                init = False
                last_valid_row = row
                continue

            diff = False  # flag to indicate if the current column is different from the last valid
            for column in columns:  # compare value by value
                if row[column] != last_valid_row[column]:
                    # column is different
                    last_valid_row = row
                    diff = True

                    break
            if not diff:  # there's no difference between columns, so this one needs to be deleted
                del_array[duplicates] = index
                duplicates += 1

    print(f"Duplicated lines {duplicates} from {len(df)}, ({100*duplicates/len(df):.02f} %)")
    del_array = del_array[:duplicates]  # keep only the part of the array that has been filled
    rich.print("dropping rows...")
    df.drop(del_array, inplace=True)
    return df


def avoid_filename_collision(filename):
    """
    Takes a filename (e.g. data.txt) and converts it to an available filename (e.g. data(1).txt).
    """
    i = 1
    a = filename.split(".")
    a[0] = a[0] + f"({i})"
    filename = ".".join(a)
    while os.path.isfile(filename):
        i += 1
        filename = filename.split("(")[0] + f"({i})" + filename.split(")")[1]
    return filename


def merge_dicts(strong: dict, weak: dict):
    """
    Merges two dictionaries. If a duplicated field is detected the 'strong' value will prevail
    """
    out = weak.copy()
    out.update(strong)
    return out


def get_file_list(dir_name):
    """
     create a list of file and sub directories names in the given directory
     :param dir_name: directory name
     :returns: list of all files with relative path
     """
    file_list = os.listdir(dir_name)
    all_files = list()
    for entry in file_list:
        full_path = os.path.join(dir_name, entry)
        if os.path.isdir(full_path):
            all_files = all_files + get_file_list(full_path)
        else:
            all_files.append(full_path)
    return all_files
