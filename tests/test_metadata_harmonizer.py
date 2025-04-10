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
import rich
import unittest
import subprocess
import sys
import time
import inspect
import yaml


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
        # Process all example datasets
        cls.example_datasets = []
        examples = sorted(os.listdir("../examples"))
        examples = [os.path.join("../examples", d) for d in examples]
        examples = [d for d in examples if os.path.isdir(d)]  # keep only directories

        for example in examples:
            files = [os.path.join(example, f) for f in os.listdir(example)]
            files = sorted(files)
            csv_files = [f for f in files if f.endswith(".csv")]
            min_meta_files = [f for f in files if f.endswith(".min.json")]
            with open(os.path.join(example, "README.yaml")) as f:
                info = yaml.safe_load(f)
                title = info["title"]
            dataset_id = os.path.basename(example) + "_" + title.replace(" ", "_")

            cls.example_datasets.append({
                "data": csv_files,
                "metadata": min_meta_files,
                "folder": os.path.basename(example),
                "dataset_id": dataset_id
            })

        os.makedirs("erddapData", exist_ok=True)
        os.makedirs("datasets", exist_ok=True)
        rich.print("Starting erddap docker container...")
        run_subprocess("docker compose up -d")

        cls.datasets_default_xml = os.path.join("conf", "datasets_default.xml")
        cls.datasets_xml = os.path.join("conf", "datasets.xml")
        shutil.copy2(cls.datasets_default_xml, cls.datasets_xml)

        rich.print(cls.example_datasets)
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
            rich.print(f"    Creating dataset {dataset['dataset_id']}...", end="")
            erddap_dataset_folder = os.path.join("datasets", dataset["folder"])
            os.makedirs(erddap_dataset_folder, exist_ok=True)
            dataset_nc = os.path.join(erddap_dataset_folder, dataset["dataset_id"] + ".nc")
            generate_dataset(dataset["data"], dataset["metadata"], output=dataset_nc)
            dataset["file"] = dataset_nc
            rich.print("[green]success!")


    def test_02_config_erddap(self):
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

            rich.print("now wait of erddap to process this flag...")

            while os.path.exists(dataset_hard_flag):
                time.sleep(1)
                rich.print("waiting for erddap to load the dataset...")

            time.sleep(3)
            dataset_url = self.erddap_url + "/tabledap/" + dataset_id + ".html"

            rich.print(dataset_url)
            urllib.request.urlretrieve(dataset_url)
            rich.print("[green]Dataset downloaded!")

            # now try to acess the data
            dataset_url = self.erddap_url + "/tabledap/" + dataset_id + ".nc"
            nc_file = "test.nc"
            urllib.request.urlretrieve(dataset_url, nc_file)
            wf = load_data(nc_file)
            df = wf.data
            rich.print("Dataset opened as NetCDF!")


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
    unittest.main(failfast=True, verbosity=1)