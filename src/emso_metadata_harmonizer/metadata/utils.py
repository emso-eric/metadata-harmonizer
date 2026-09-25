#!/usr/bin/env python3
"""
Miscellaneous functions

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 26/4/23
"""
import hashlib
from logging.handlers import TimedRotatingFileHandler
from typing import Optional, Dict

import requests
import rich
import concurrent.futures as futures
import os
import logging

from requests import HTTPError

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

EMH_LOGGER_NAME = "emso_metadata_harmonizer"

logger = logging.getLogger(EMH_LOGGER_NAME)


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

        if "variable_type" not in var.keys():
            vartype = "unclassified"
        else:
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


def download_file(url: str, filename: str, headers: Optional[Dict[str, str]] = None, chunk_size: int = 8192, alternative="") -> None:
    """
    Download a file from a URL and save it to disk.

    Args:
        url: The URL to download from
        filename: The local path where to save the file
        headers: Optional HTTP headers to include in the request
        chunk_size: Size of chunks to stream the download (default 8KB)
        alternative: Alternative URI to download in case the url fails
    """
    try:
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; DataDownloader/1.0)',
                'Accept': '*/*'
            }

        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()

        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)

        with open(filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    file.write(chunk)
    except (HTTPError, requests.exceptions.ConnectionError) as e:
        if alternative:
            logger.warning(f"Failed to fetch URL, using alternative {alternative}")
            download_file(alternative, filename, headers=headers, chunk_size=chunk_size, alternative="")
        else:
            logger.error(f"Failed to fetch URL {url}")
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

def get_dir_list(dir_name):
    """
     create a list of file and sub directories names in the given directory
     :param dir_name: directory name
     :returns: list of all files with relative path
     """
    file_list = os.listdir(dir_name)
    all_dirs = list()
    for entry in file_list:
        full_path = os.path.join(dir_name, entry)
        if os.path.isdir(full_path):
            all_dirs.append(full_path)
            all_dirs = all_dirs + get_dir_list(full_path)

    all_dirs = sorted(all_dirs, reverse=True)
    return all_dirs


class LoggerSuperclass:
    def __init__(self, name: str, colour=NRM):
        """
        SuperClass that defines logging as class methods adding a heading name
        """
        self._logger_name = name
        self.logger = logging.getLogger(EMH_LOGGER_NAME)
        self._log_colour = colour

    def warning(self, *args):
        mystr = YEL + "[%s] " % self._logger_name + str(*args) + RST
        self.logger.warning(mystr)

    def error(self, *args, exception: any = False):
        mystr = "[%s] " % self._logger_name + str(*args)
        self.logger.error(RED + mystr + RST)
        if exception:
            if isinstance(exception, bool):
                raise ValueError(mystr)
            else:
                raise exception(mystr)

    def debug(self, *args):
        mystr = self._log_colour + "[%s] " % self._logger_name + str(*args) + RST
        self.logger.debug(mystr)

    def info(self, *args):
        mystr = self._log_colour + "[%s] " % self._logger_name + str(*args) + RST
        self.logger.info(mystr)

    def setLevel(self, level):
        self.logger.setLevel(level)




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

    logger = logging.getLogger(EMH_LOGGER_NAME)
    logger.setLevel(level)
    log_formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)-7s: %(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')
    handler = TimedRotatingFileHandler(filename, when="midnight", interval=1, backupCount=7)
    handler.setFormatter(log_formatter)
    logger.addHandler(handler)

    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(log_formatter)
    logger.addHandler(consoleHandler)
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

def assert_url(url: str):
    assert url.startswith("http"), f"Not a valid URL: {url}"


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

def get_file_md5(filename):
    md5_hash = hashlib.md5()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b""):
            md5_hash.update(chunk)

    return md5_hash.hexdigest()


import os
import subprocess
import tempfile
from datetime import datetime


def get_tags_by_date(owner, repo, newest_first=True, timeout=120):
    """Return a list of (tag_name, datetime) for a public GitHub repo."""
    url = f"https://github.com/{owner}/{repo}.git"
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # never hang on a login prompt
    sort = "-creatordate" if newest_first else "creatordate"

    with tempfile.TemporaryDirectory() as tmp:
        def git(*args):
            return subprocess.run(
                ["git", *args], cwd=tmp, env=env, timeout=timeout,
                check=True, capture_output=True, text=True,
            ).stdout

        git("init", "--quiet", "--bare")
        git("fetch", "--quiet", "--depth=1", "--filter=tree:0", "--no-tags",
            url, "refs/tags/*:refs/tags/*")
        # creatordate = tagger date for annotated tags, commit date otherwise
        out = git("for-each-ref", f"--sort={sort}",
                  "--format=%(refname:short)%09%(creatordate:iso-strict)",
                  "refs/tags")

    tags = []
    for line in out.splitlines():
        name, _, date = line.partition("\t")
        tags.append((name, datetime.fromisoformat(date) if date else None))
    return tags

"""Get the highest x.y.z version tag of a public GitHub repo.

No clone, no token, no third-party packages, no git executable needed:
pure Python standard library, so it runs the same on Windows, macOS and Linux.

It reads Git's own "smart HTTP" ref advertisement - the same endpoint
`git ls-remote` uses. It lists every tag name in a single small request and
is not subject to the GitHub REST API's 60-requests/hour anonymous limit.
"""
import re
import shutil
import subprocess
import urllib.request

# Accepts "1.2.3" and "v1.2.3"; rejects "1.2", "1.2.3-rc1", "1.2.3.dev0", etc.
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _tags_via_http(owner, repo, timeout):
    url = f"https://github.com/{owner}/{repo}.git/info/refs?service=git-upload-pack"
    req = urllib.request.Request(url, headers={"User-Agent": "git/2.0 (python)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()

    # Parse Git pkt-line format: 4 hex digits = length (incl. those 4), "0000" = flush.
    tags, pos = [], 0
    while pos + 4 <= len(data):
        length = int(data[pos:pos + 4], 16)
        if length == 0:
            pos += 4
            continue
        line = data[pos + 4:pos + length].decode("utf-8", "replace")
        pos += length
        line = line.split("\0", 1)[0].rstrip("\n")  # drop capabilities
        _, _, ref = line.partition(" ")
        if ref.startswith("refs/tags/") and not ref.endswith("^{}"):
            tags.append(ref[len("refs/tags/"):])
    return tags


def _tags_via_git(owner, repo, timeout):
    out = subprocess.run(
        ["git", "ls-remote", "--tags", "--refs",
         f"https://github.com/{owner}/{repo}.git"],
        capture_output=True, text=True, check=True, timeout=timeout,
        env={**__import__("os").environ, "GIT_TERMINAL_PROMPT": "0"},
    ).stdout
    return [line.split("refs/tags/", 1)[1] for line in out.splitlines()
            if "refs/tags/" in line]


def list_tags(owner, repo, timeout=30):
    """All tag names. Pure HTTP first; `git ls-remote` as fallback if installed."""
    try:
        return _tags_via_http(owner, repo, timeout)
    except Exception as http_err:
        if shutil.which("git"):
            try:
                return _tags_via_git(owner, repo, timeout)
            except Exception:
                pass
        raise RuntimeError(
            f"Could not list tags for {owner}/{repo} "
            "(repo missing/private, or no network)") from http_err


def git_latest_version(owner, repo, timeout=30):
    """Return the tag with the highest x.y.z version (e.g. 'v2.34.2'), or None."""
    best_key, best_tag = None, None
    for tag in list_tags(owner, repo, timeout):
        m = VERSION_RE.match(tag)
        if m:
            key = tuple(int(n) for n in m.groups())  # numeric: 1.10.0 > 1.9.0
            if best_key is None or key > best_key:
                best_key, best_tag = key, tag
    return best_tag

