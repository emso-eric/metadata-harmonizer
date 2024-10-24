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
from argparse import ArgumentParser
import rich
import unittest
import subprocess
import sys
import time
import json
import pandas as pd
import inspect

try:
    from src.emso_metadata_harmonizer import generate_dataset, erddap_config
    from src.emso_metadata_harmonizer.metadata.dataset import load_data
except ModuleNotFoundError:
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the parent directory (project root)
    parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    # Add the parent directory to the sys.path
    sys.path.insert(0, parent_dir)
    from src.emso_metadata_harmonizer import generate_dataset, erddap_config
    from src.emso_metadata_harmonizer.metadata.dataset import load_data
    from src.emso_metadata_harmonizer.metadata.emso import EmsoMetadata


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
        os.makedirs("erddapData", exist_ok=True)
        rich.print("Starting erddap docker container...")
        run_subprocess("docker compose up -d")

        cls.two_ctds_dataset = "erddapData/2CTDs/2ctds_dataset.nc"
        cls.datasets_default_xml = os.path.join("conf", "datasets_default.xml")
        cls.datasets_xml = os.path.join("conf", "datasets.xml")
        shutil.copy2(cls.datasets_default_xml, cls.datasets_xml)

        cls.dataset_id = "2CTDs"

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

    def test_01_create_dataset(self):
        """Creates a dataset based on examples files"""
        rich.print(f"[purple]Running test {inspect.currentframe().f_code.co_name}")
        metadata_files = [
            "../examples/2CTDs/SBE16.min.json",
            "../examples/2CTDs/SBE37.min.json"
        ]

        data_files = [
            "../examples/2CTDs/SBE16.csv",
            "../examples/2CTDs/SBE37.csv"
        ]

        os.makedirs(os.path.dirname(self.two_ctds_dataset), exist_ok=True)
        generate_dataset(data_files, metadata_files, autofill=False, output=self.two_ctds_dataset)
        wf = load_data(self.two_ctds_dataset)
        self.assertTrue(os.path.exists(self.two_ctds_dataset))

    def test_02_create_dataset_from_dict(self):
        """Creates a dataset based on examples files"""
        rich.print(f"[purple]Running test {inspect.currentframe().f_code.co_name}")
        metadata_files = [
            "../examples/2CTDs/SBE16.min.json",
            "../examples/2CTDs/SBE37.min.json"
        ]

        data_files = [
            "../examples/2CTDs/SBE16.csv",
            "../examples/2CTDs/SBE37.csv"
        ]

        metadata = []  # convert metadata files to dicts
        for m in metadata_files:
            with open(m) as f:
                metadata.append(json.load(f))

        # convert data files to DataFrames
        data = [pd.read_csv(f) for f in data_files]

        os.makedirs(os.path.dirname(self.two_ctds_dataset), exist_ok=True)
        generate_dataset(data, metadata, autofill=False, output=self.two_ctds_dataset)
        # Create it two times, to ensure that the original data is not broken!
        generate_dataset(data, metadata, autofill=False, output=self.two_ctds_dataset)

        wf = load_data(self.two_ctds_dataset)
        self.assertTrue(os.path.exists(self.two_ctds_dataset))

        # Now create a dataset with an existing instance of EmsoMetadata
        emso = EmsoMetadata()
        generate_dataset(data, metadata, autofill=False, output=self.two_ctds_dataset, emso_metadata=emso)

        # Now do the same, but delete a mandatory element from metadata, we should get a ValueError
        metadata[0]["global"]["$site_code"] = ""
        with self.assertRaises(ValueError):
            generate_dataset(data, metadata, autofill=False, output=self.two_ctds_dataset)


    def test_03_config_erddap(self):
        """
        Configure the ERDDAP dataset for the new sensor
        """
        rich.print(f"[purple]Running test {inspect.currentframe().f_code.co_name}")
        # def erddap_config(file: str, dataset_id: str, source_path: str, output: str = "", datasets_xml: str = ""):
        data_path = os.path.join("/erddapData", self.dataset_id)
        erddap_config(self.two_ctds_dataset,
                      "2CTDs",
                      data_path,
                      datasets_xml_file=self.datasets_xml)

        rich.print("Creating a hardFlag to force reload")
        dataset_hard_flag = os.path.join("erddapData", "hardFlag", self.dataset_id)
        with open(dataset_hard_flag, "w") as f:
            f.write("1")

        rich.print("now wait of erddap to process this flag...")

        while os.path.exists(dataset_hard_flag):
            time.sleep(1)
            rich.print("waiting for erddap to load the dataset...")

        time.sleep(3)
        dataset_url = self.erddap_url + "/tabledap/" + self.dataset_id + ".html"

        rich.print(dataset_url)
        urllib.request.urlretrieve(dataset_url)
        rich.print("[green]Dataset downloaded!")

        # now try to acess the data
        dataset_url = self.erddap_url + "/tabledap/" + self.dataset_id + ".nc"
        nc_file = "test.nc"
        urllib.request.urlretrieve(dataset_url, nc_file)
        wf = load_data(nc_file)
        df = wf.data


    @classmethod
    def tearDownClass(cls):
        rich.print("clearing datasets.xml backups...")
        files = os.listdir()
        for f in files:
            if f.startswith(".datasets.xml."):
                os.remove(f)
        rich.print("[green]ok")

        os.system("docker compose down")
        rich.print("Clearing ERDDAP volume...")
        os.system("rm -rf erddapData/*")
        rich.print(f"[green]done")


if __name__ == "__main__":
    unittest.main(failfast=True, verbosity=1)