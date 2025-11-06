#!/usr/bin/env python3
"""
Miscellaneous functions

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 26/4/23
"""
from logging.handlers import TimedRotatingFileHandler
import requests
import rich
from rich.progress import Progress
import urllib
import concurrent.futures as futures
import os
from .constants import dimensions
import logging

# Color codes
GRN = "\x1B[32m"
RST = "\033[0m"
BLU = "\x1B[34m"
YEL = "\x1B[33m"
RED = "\x1B[31m"
MAG = "\x1B[35m"
CYN = "\x1B[36m"
WHT = "\x1B[37m"
NRM = "\x1B[0m"
PRL = "\033[95m"
RST = "\033[0m"


def group_metadata_variables(metadata):
    """
    Takes a dictionary with all the variables and groups them according to their variable_type attribute
    """

    m = metadata.copy()

    d = {
        "global": {"global": m["global"]},  # add an additional global level to keep the same structure
        "coordinate": {},
        "environmental": {},
        "biological": {},
        "quality_control": {},
        "technical": {},
        "platform": {},
        "sensor": {},

        "unclassified": {},  # Unclassified variables are ALL errors!
    }

    for varname, var in m["variables"].items():
        if "variable_type" not in var.keys():
            d["unclassified"][varname] = var

        vartype = var["variable_type"]

        if vartype not in d.keys():
            d["unclassified"][varname] = var
        else:
            d[vartype][varname] = var

    for section in d.keys():
        for varname in d[section].keys():
            d[section][varname]["$name"] = varname

    return d


def __threadify_index_handler(index, handler, args):
    """
    This function adds the index to the return of the handler function. Useful to sort the results of a
    multithreaded operation
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


class LoggerSuperclass:
    def __init__(self, logger: logging.Logger, name: str, colour=NRM):
        """
        SuperClass that defines logging as class methods adding a heading name
        """
        self.__logger_name = name
        self.__logger = logger
        if not logger:
            self.__logger = logging  # if not assign the generic module
        self.__log_colour = colour

    def warning(self, *args):
        mystr = YEL + "[%s] " % self.__logger_name + str(*args) + RST
        self.__logger.warning(mystr)

    def error(self, *args, exception: any = False):
        mystr = "[%s] " % self.__logger_name + str(*args)
        self.__logger.error(RED + mystr + RST)
        if exception:
            if isinstance(exception(), Exception):
                raise exception(mystr)
            else:
                raise ValueError(mystr)


    def debug(self, *args):
        mystr = self.__log_colour + "[%s] " % self.__logger_name + str(*args) + RST
        self.__logger.debug(mystr)

    def info(self, *args):
        mystr = self.__log_colour + "[%s] " % self.__logger_name + str(*args) + RST
        self.__logger.info(mystr)

    def setLevel(self, level):
        self.__logger.setLevel(level)


def setup_log(name, path="log", log_level="debug"):
    """
    Setups the logging module
    :param name: log name (.log will be appended)
    :param path: where the logs will be stored
    :param log_level: log level as string, it can be "debug, "info", "warning" and "error"
    """

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Check arguments
    if len(name) < 1 or len(path) < 1:
        raise ValueError("name \"%s\" not valid", name)
    elif len(path) < 1:
        raise ValueError("name \"%s\" not valid", name)

    # Convert to logging level
    if log_level == 'debug':
        level = logging.DEBUG
    elif log_level == 'info':
        level = logging.INFO
    elif log_level == 'warning':
        level = logging.WARNING
    elif log_level == 'error':
        level = logging.ERROR
    else:
        raise ValueError("log level \"%s\" not valid" % log_level)

    if not os.path.exists(path):
        os.makedirs(path)

    filename = os.path.join(path, name)
    if not filename.endswith(".log"):
        filename += ".log"
    print("Creating log", filename)
    print("name", name)

    logger = logging.getLogger()
    logger.setLevel(level)
    log_formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)-7s: %(message)s',
                                      datefmt='%Y/%m/%d %H:%M:%S')
    handler = TimedRotatingFileHandler(filename, when="midnight", interval=1, backupCount=7)
    handler.setFormatter(log_formatter)
    logger.addHandler(handler)

    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(log_formatter)
    logger.addHandler(consoleHandler)

    logger.info("")
    logger.info(f"===== {name} =====")

    return logger


def assert_dict(conf: dict, required_keys: dict, verbose=False):
    """
    Checks if all the expected keys in a dictionary are there. The expected format is field name as key and type as
    value:
        { "name": str, "importantNumber": int}

    One level of nesting is supported:
    value:
        { "someData/nestedData": str}
    expects something like
        {
        "someData": {
            "nestedData": "hi"
            }
        }

    :param conf: dict with configuration to be checked
    :param required_keys: dictionary with required keys
    :raises: AssertionError if the input does not match required_keys
    """
    for key, expected_type in required_keys.items():
        if "/" in key:
            pass
        elif key not in conf.keys():
            raise AssertionError(f"Required key \"{key}\" not found in configuration")

        # Check for nested dicts
        if "/" in key:
            parent, son = key.split("/")
            if parent not in conf.keys():
                msg =f"Required key \"{parent}\" not found!"
                if verbose:
                    rich.print(f"[red]{msg}")
                raise AssertionError(msg)

            if type(conf[parent]) != dict:
                msg = f"Value for key \"{parent}\" wrong type, expected type dict, but got {type(conf[parent])}"
                if verbose:
                    rich.print(f"[red]{msg}")
                raise AssertionError(msg)
            if son not in conf[parent].keys():
                msg =f"Required key \"{son}\" not found in configuration/{parent}"
                if verbose:
                    rich.print(f"[red]{msg}")
                raise AssertionError(msg)
            value = conf[parent][son]
        else:
            value = conf[key]

        if type(value) != expected_type:
            msg = f"Value for key \"{key}\" wrong type, expected type {expected_type}, but got '{type(value)}'"
            if verbose:
                rich.print(f"[red]{msg}")
            raise AssertionError(msg)


def assert_type(obj, valid_type):
    """
    Asserts that obj is of type <valid_type>
    :param obj:  any object
    :param valid_type:  any type
    """
    assert isinstance(obj, valid_type), f"Expected {valid_type}, but got {type(obj)} instead"


def assert_types(obj, valid_types: list):
    """
    Asserts that obj is of type <valid_type>
    :param obj:  any object
    :param valid_types:  list of types
    """
    assert isinstance(valid_types, list), "valid_types should be a list of types!"
    valid_string = ", ".join([str(t) for t in valid_types])
    valid_string = valid_string.replace("<class ", "").replace(">", "")
    assert type(obj) in valid_types, f"Expected on of {valid_string}, but got {type(obj)} instead"


def check_url(url):
    """
    Checks if a URL is reachable without downloading its contents
    """
    assert type(url) is str, f"Expected string got {type(url)}"
    try:
        response = requests.head(url)
        if response.status_code == 200:
            return True
        else:
            return False
    except requests.ConnectionError:
        return False

