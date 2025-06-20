#!/usr/bin/env python3
"""

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 6/6/24
"""

import os
import shutil
import urllib
import warnings

import rich
import unittest
import subprocess
import sys
import time
import inspect
import logging

from cfchecker.cfchecks import CFChecker

try:
    from src.emso_metadata_harmonizer import generate_dataset, erddap_config, WaterFrame
    from src.emso_metadata_harmonizer.metadata.dataset import load_data
    from src.emso_metadata_harmonizer.metadata.utils import setup_log

except ModuleNotFoundError:
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the parent directory (project root)
    parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    # Add the parent directory to the sys.path
    sys.path.insert(0, parent_dir)
    from src.emso_metadata_harmonizer import generate_dataset, erddap_config, WaterFrame, setup_log
    from src.emso_metadata_harmonizer.metadata.dataset import load_data
    from src.emso_metadata_harmonizer.metadata.emso import EmsoMetadata
    from src.emso_metadata_harmonizer.metadata import setup_log


def run_subprocess(cmd):
    """
    Runs a command as a subprocess. If the process retunrs 0 returns True. Otherwise prints stderr and stdout and returns False
    :param cmd: command (list or string)
    :return: True/False
    """
    assert (type(cmd) is list or type(cmd) is str)
    if type(cmd) == list:
        cmd_list = cmd
    else:
        cmd_list = cmd.split(" ")
    proc = subprocess.run(cmd_list, capture_output=True)
    if proc.returncode != 0:
        rich.print(f"\n[red]ERROR while running command '{cmd}'")
        if proc.stdout:
            rich.print(f"subprocess stdout:")
            rich.print(f">[bright_black]    {proc.stdout.decode()}")
        if proc.stderr:
            rich.print(f"subprocess stderr:")
            rich.print(f">[bright_black] {proc.stderr.decode()}")

        raise ValueError(f"subprocess failed: {cmd_list}")


class MetadataHarmonizerTester(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Process all example datasets
        cls.example_datasets = []
        logger = logging.getLogger("emh")
        cls.log = logger
        examples = sorted(os.listdir("../examples"))
        examples = [e for e in examples if not e.startswith("example")]
        examples = [os.path.join("../examples", d) for d in examples]
        examples = [d for d in examples if os.path.isdir(d)]  # keep only directories

        for example in examples:
            files = [os.path.join(example, f) for f in os.listdir(example)]
            files = sorted(files)
            csv_files = [f for f in files if f.endswith(".csv")]
            min_meta_files = [f for f in files if f.endswith(".yaml")]

            dataset_id = os.path.basename(example)

            cls.example_datasets.append({
                "data": csv_files,
                "metadata": min_meta_files,
                "folder": os.path.basename(example),
                "dataset_id": dataset_id
            })

        os.makedirs("erddapData", exist_ok=True)
        os.makedirs("datasets", exist_ok=True)

        rich.print("Removing previous datasets...")
        for folder in [os.path.join("datasets", d) for d in os.listdir("datasets")]:
            files = [os.path.join(folder, f) for f in os.listdir(folder)]
            for f in files:
                os.remove(f)
            os.rmdir(folder)

        rich.print("Starting erddap docker container...")
        run_subprocess("docker compose up -d")

        cls.datasets_default_xml = os.path.join("conf", "datasets_default.xml")
        cls.datasets_xml = os.path.join("conf", "datasets.xml")
        shutil.copy2(cls.datasets_default_xml, cls.datasets_xml)

        cls.erddap_url = "http://localhost:8080/erddap"
        erddap_up = False
        while not erddap_up:
            try:
                urllib.request.urlretrieve(cls.erddap_url)
                erddap_up = True
            except urllib.error.URLError:
                rich.print("waiting for ERDDAP to start...")
                time.sleep(2)
            except ConnectionError:
                rich.print("waiting for ERDDAP to start...")
                time.sleep(2)

    def test_01_create_datasets(self):
        """Creates a dataset based on examples files"""
        rich.print(f"[purple]Running test {inspect.currentframe().f_code.co_name}")

        # Get a list of all example datasets
        for dataset in self.example_datasets:
            erddap_dataset_folder = os.path.join("datasets", dataset["folder"])
            os.makedirs(erddap_dataset_folder, exist_ok=True)
            dataset_nc = os.path.join(erddap_dataset_folder, dataset["dataset_id"] + ".nc")
            generate_dataset(dataset["data"], dataset["metadata"], dataset_nc, self.log)
            dataset["file"] = dataset_nc

    def test_02_cf_compliance(self):
        rich.print(f"Checking CF compliance")
        for dataset in self.example_datasets:
            cf = CFChecker(silent=True)
            file = dataset["file"]
            rich.print(f"\n==== Checking CF compliance of {dataset["dataset_id"]} ====")
            errors = 0
            warns = 0
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=DeprecationWarning)
                cf.checker(file)
            for msg in cf.all_messages:
                if msg.startswith("INFO:"):
                    rich.print(f"[cyan]{msg}")
                elif msg.startswith("WARN:"):
                    rich.print(f"[yellow]{msg}")
                    warns += 1
                elif msg.startswith("ERROR:"):
                    rich.print(f"[red]{msg}")
                    errors += 1
                else:
                    rich.print(f"[white]{msg}")
            if errors > 0:
                ValueError(f"Got {errors} in CF compliance")

    def test_03_config_erddap(self):
        """
        Configure the ERDDAP dataset for the new sensor
        """
        rich.print(f"[purple]Running test {inspect.currentframe().f_code.co_name}")
        for dataset in self.example_datasets:
            dataset_id = dataset["dataset_id"]
            erddap_dataset_folder = os.path.join("datasets", dataset["folder"])
            # Convert current path to ERDDAP docker path
            erddap_container_path = f"/datasets/{os.path.basename(erddap_dataset_folder)}"  # Convert real path to conatiner path
            erddap_config(
                dataset["file"],
                dataset_id,
                erddap_container_path,
                datasets_xml_file=self.datasets_xml
            )
            rich.print("Creating a hardFlag to force reload")
            dataset_hard_flag = os.path.join("erddapData", "hardFlag", dataset_id)

            with open(dataset_hard_flag, "w") as f:
                f.write("1")

        for dataset in self.example_datasets:
            dataset_id = dataset["dataset_id"]
            # Convert current path to ERDDAP docker path
            dataset_hard_flag = os.path.join("erddapData", "hardFlag", dataset_id)
            rich.print("now wait of erddap to process this flag...")

            while os.path.exists(dataset_hard_flag):
                time.sleep(1)
                rich.print(f"waiting for erddap to load dataset {dataset_id}...")

            init = time.time()
            dataset_url = self.erddap_url + "/tabledap/" + dataset_id + ".html"
            rich.print(dataset_url)
            urllib.request.urlretrieve(dataset_url)
            downloaded = False
            while time.time() - init < 60:
                try:
                    urllib.request.urlretrieve(dataset_url)
                    downloaded = True
                    break
                except urllib.error.HTTPError:
                    time.sleep(1)

            if not downloaded:
                raise ValueError(f"Could not download {dataset_url}")

            rich.print("[green]Dataset downloaded!")

            # now try to acess the data
            dataset_url = self.erddap_url + "/tabledap/" + dataset_id + ".nc"
            nc_file = "mytest.nc"
            urllib.request.urlretrieve(dataset_url, nc_file)
            wf = WaterFrame.from_netcdf(nc_file)
            df = wf.data
            rich.print("Dataset opened as NetCDF!")
            os.remove(nc_file)


    @classmethod
    def tearDownClass(cls):
        rich.print("clearing datasets.xml backups...")
        files = os.listdir()
        for f in files:
            if f.startswith(".datasets.xml."):
                os.remove(f)
        rich.print("[green]ok")

        # os.system("docker compose down")
        # rich.print("Clearing ERDDAP volume...")
        # os.system("rm -rf erddapData/*")
        # rich.print(f"[green]done")


if __name__ == "__main__":
    logger = setup_log("emh")
    logger.setLevel(logging.INFO)

    unittest.main(failfast=True, verbosity=1)
