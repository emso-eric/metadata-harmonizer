#!/usr/bin/env python3
"""
This file implements the tests to ensure that a dataset is harmonized. To include a new tests simply add a new method
like
 my_new_test(self, value, args) -> (bool, str)

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 1/3/23
"""

import rich
from rich.console import Console
from rich.table import Table
from rich.style import Style
from rich.progress import Progress
import pandas as pd
import re
from . import EmsoMetadata
from .utils import group_metadata_variables
import inspect
import numpy as np

class EmsoMetadataTester:
    def __init__(self):
        """
        This class implements the tests to ensure that the metadata in a particular ERDDAP is harmonized with the EMSO
        metadata standards. The tests are configured in the 'EMSO_metadata.md' document. There should be 2 different
        tables with the tests defined, one for the global attributes and another one for tests to be carreid
        """
        # Dict to store all erddap. KEY is the test identifier while value is the method
        rich.print("[blue]Setting up EMSO Metadata Tests...")

        self.metadata = EmsoMetadata(True)

        self.implemented_tests = {}
        for name, element in inspect.getmembers(self):
            if name == "validate_dataset":  # exclude validate dataset from tests
                continue
            # Assume that all methods not starting with "_" are tests!
            elif inspect.ismethod(element) and not name.startswith("_"):
                self.implemented_tests[name] = element

        rich.print(f"Currently there are {len(self.implemented_tests)} tests implemented")

        # ensure that all required test are implemented...
        all_tests = list(self.metadata.global_attr["Compliance test"].values)
        all_tests += list(self.metadata.variable_attr["Compliance test"].values)
        all_tests = [value.split("#")[0] for value in all_tests]
        all_tests = np.unique(all_tests)
        error = False
        for test in all_tests:
            if test not in self.implemented_tests.keys():
                rich.print(f"[red]ERROR test {test} not implemented!")
                error = True
        if error:
            raise ValueError("Some tests are not implemented")

    def __process_results(self, df, verbose=False) -> (float, float, float):
        """
        Prints the results in a nice-looking table using rich
        :param df: DataFrame with test results
        """
        table = Table(title="Dataset Test Report")
        table.add_column("variable", justify="right", no_wrap=True, style="cyan")
        table.add_column("attribute", justify="right")
        table.add_column("required", justify="right")
        table.add_column("passed", justify="right")
        table.add_column("message", justify="right")
        table.add_column("value", justify="left")
        section = "global"
        for _, row in df.iterrows():
            # Process styles depending on the passed and required fields
            style = ""
            if row["message"] == "unimplemented":
                style = Style(color="bright_black", bold=False)
            elif row["message"] == "not defined":
                style = Style(color="medium_purple4", bold=False)
            elif row["required"] and not row["passed"]:
                style = Style(color="red", bold=True)
            elif row["passed"]:
                style = Style(color="green", bold=True)
            elif not row["required"] and not row["passed"]:
                style = Style(color="yellow", bold=False)

            if row["variable"] != section:  # add a new empty row with end section
                section = row["variable"]
                table.add_row(style=style, end_section=True)

            variable = row["variable"]
            attribute = row["attribute"]
            required = str(row["required"])
            passed = str(row["passed"])
            message = row["message"]
            value = str(row["value"])
            table.add_row(variable, attribute, required, passed, message, value, style=style)

        console = Console()
        console.print(table)

        df["required"] = df["required"].astype(bool)
        df["passed"] = df["passed"].astype(bool)

        r = df[df["required"]]  # required test
        req_tests = len(r)
        req_passed = len(r[r["passed"]])

        o = df[df["required"] == False]  # required test
        opt_tests = len(o)
        opt_passed = len(o[o["passed"]])

        total_tests = len(df)
        total_passed = len(df[df["passed"]])
        rich.print(f"Required tests passed: {req_passed} of {req_tests}")
        rich.print(f"Required tests passed: {opt_passed} of {opt_tests}")
        rich.print(f"   [bold]Total tests passed: {total_passed} of {total_tests}")

        def generate_bar_col(n):
            if n > 0.95:
                return "green"
            if n > 0.8:
                return "blue"
            if n > 0.6:
                return "yellow"
            if n > 0.4:
                return "dark_orange"
            return "red"

        t_color = generate_bar_col(total_passed / total_tests)
        r_color = generate_bar_col(req_passed / req_tests)
        o_color = generate_bar_col(opt_passed / opt_tests)

        with Progress(auto_refresh=False) as progress:
            req_task = progress.add_task(f"[{t_color}]Required tests...", total=req_tests)
            opt_task = progress.add_task(f"[{r_color}]Optional tests...", total=opt_tests)
            total_task = progress.add_task(f"[{o_color}]Total tests...", total=total_tests)

            progress.update(req_task, advance=req_passed)
            progress.update(opt_task, advance=opt_passed)
            progress.update(total_task, advance=total_passed)
            progress.stop()
        total = 100*round(total_passed / total_tests, 2)
        required = 100*round(req_passed / req_tests, 2)
        optional = 100*round(opt_passed / opt_tests, 2)

        return total, required, optional

    def __run_test(self, test_name, args, attribute: str, metadata, required, multiple, varname, results) -> (
    bool, str, any):
        """
        Applies the method test to the dict data and stores the output into results
        :param test_name: Name of the test tp apply
        :param args: arguments to be passed to test_method
        :param attribute: name of the attribute to be tested
        :param metadata: dict with the metadata being tested
        :param required: flag indicating if test is mandatory
        :param multiple: If set, multiple values separated by ; are allowed for this metadata field
        :param varname: variable name for the applied test (global for generic dataset metadata)
        :param results: dict with arrays to store the results of the tests
        :return: a tuple with (bool, str, any). Boolean indicates success, str is an error message and any is the value
                 of the attribute or None if not present.
        """

        if attribute == "$name" or attribute in metadata.keys():
            if test_name not in self.implemented_tests.keys():
                rich.print(f"[red]Test '{test_name}' not implemented!")
                raise LookupError(f"Test {test_name} not found")

            if attribute == "$name":
                value = varname
            else:
                value = metadata[attribute]

            if type(value) == str and ";" in value:
                values = value.split(";")  # split multiple values
                for i in range(len(values)):
                    if values[i].startswith(" "):
                        values[i] = values[i][1:]  # Make sure that first space is not kept
            else:
                values = [value]

            if len(values) > 1 and not multiple:
                # got multiple values for a single-value test!
                passed = False
                message = f"Got {len(values)} values for a single-value test"
            else:
                messages = []
                passed_flags = []
                for v in values:
                    test_method = self.implemented_tests[test_name]
                    try:
                        p, m = test_method(v, args)  # apply test method
                    except Exception as e:
                        rich.print(
                            f"[red]Error when executing test '{test_name}' with arguments '{args}' and value '{v}'")
                        raise e
                    if not m:
                        m = "ok"  # instead of empty message just leave ok

                    messages.append(m)
                    passed_flags.append(p)
                message = "; ".join(messages)
                passed = True

                for p in passed_flags:
                    passed = p and passed
        else:  # Not found
            passed = False
            message = "not found"
            value = ""

        results["attribute"].append(attribute)
        results["variable"].append(varname)
        results["passed"].append(passed)
        results["required"].append(required)
        results["message"].append(message)
        results["value"].append(value)
        return passed, message, value

    def __test_group_handler(self, test_group: pd.DataFrame, metadata: dict, variable: str, verbose: bool, results={}
                             ) -> dict:
        """
        Takes a list of tests from the metadata specification and applies it to the metadata json structure
        :param test_group: DataFrame of the group of tests required
        :param metadata: JSON structure (dict) under test
        :param variable: Variable being tested, 'global' for global dataset attributes
        :param verbose: if True, will add attributes present in the dataset but not required by the standard.
        :param results: a dict to store the results. If empty a new one will be created
        :returns: result structure
        """
        if not results:
            results = {
                "attribute": [],
                "variable": [],
                "required": [],
                "passed": [],
                "message": [],
                "value": []
            }
        attribute_col = test_group.columns[0]

        # Run Global Attributes test
        for _, row in test_group.iterrows():
            attribute = row[attribute_col]
            test_name = row["Compliance test"]
            required = row["Required"]
            multiple = row["Multiple"]
            if not test_name:
                rich.print(f"[yellow]WARNING: test for {attribute} not implemented!")
                continue

            args = []
            if "#" in test_name:
                test_name, args = test_name.split("#")
                args = args.split(",")  # comma-separated fields are args

            self.__run_test(test_name, args, attribute, metadata, required, multiple, variable, results)

        if verbose:  # add all parameters not listed in the standard
            checks = list(test_group[attribute_col].values)
            for key, value in metadata.items():
                if key not in checks:
                    results["attribute"].append(key)
                    results["variable"].append(variable)
                    results["passed"].append("n/a")
                    results["required"].append("n/a")
                    results["message"].append("not defined")

                    if type(value) == str and len(value) > 100:
                        value = value.strip()[:60] + "..."
                    results["value"].append(value)
        return results

    def validate_dataset(self, metadata, verbose=True, store_results=False):
        """
        Takes the well-formatted JSON metadata from an ERDDAP dataset and processes it
        :param metadata: well-formatted JSON metadta for an ERDDAP dataset
        :return: a DataFrame with the following columns: [attribute, variable, required, passed, message, value]
        """

        metadata = group_metadata_variables(metadata)

        # Try to get a dataset id
        if "dataset_id" in metadata["global"].keys():
            dataset_id = metadata["global"]["dataset_id"]
        elif "id" in metadata["global"].keys():
            dataset_id = metadata["global"]["id"]
        else:
            dataset_id = metadata["global"]["title"]

        rich.print(f"#### Validating dataset [cyan]{metadata['global']['title']}[/cyan] ####")

        # Test global attributes
        results = self.__test_group_handler(self.metadata.global_attr, metadata["global"], "global", verbose)

        # Test every dimension
        for varname, var_metadata in metadata["dimensions"].items():
            if varname.lower() == "sensor_id":
                # Deliberately skip sensor_id
                continue
            # First check variable name manually

            results = self.__test_group_handler(self.metadata.dimension_attr, metadata["dimensions"][varname], varname,
                                                verbose, results)

        # Test every variable
        for varname, var_metadata in metadata["variables"].items():
            results = self.__test_group_handler(self.metadata.variable_attr, metadata["variables"][varname], varname,
                                                verbose, results)
        # Test every QC column
        for varname, var_metadata in metadata["qc"].items():
            results = self.__test_group_handler(self.metadata.qc_attr, metadata["qc"][varname], varname,
                                                verbose, results)

        for varname, var_metadata in metadata["technical"].items():
            results = self.__test_group_handler(self.metadata.technical_attr, metadata["technical"][varname], varname,
                                                verbose, results)

        df = pd.DataFrame(results)
        total, required, optional = self.__process_results(df, verbose=verbose)
        r = {
            "dataset_id": dataset_id,
            "institution": "unknown",
            "emso_facility": "",
            "total": total,
            "required": required,
            "optional": optional
        }

        if "institution" in metadata["global"].keys():
            r["institution"] = metadata["global"]["institution"]
        elif "institution_edmo_codi" in metadata["global"].keys():
            r["institution"] = "EMDO Code " + metadata["global"]["institution_edmo_codi"]
        else:
            r["institution"] = "unknown"

        # Add EMSO Facility in results
        if "emso_facility" in metadata["global"].keys():
            r["emso_facility"] = metadata["global"]["emso_facility"]

        if store_results:
            results_csv = f"report_{dataset_id}.csv".replace(" ", "_").replace(",", "")
            rich.print(f"[green]Storing results into file {results_csv}...")
            df.to_csv(results_csv, index=False)
        return r

    # ------------------------------------------------ TEST METHODS -------------------------------------------------- #
    # Test methods implement checks to be applied to a group metadata attributes, such as coordinates or valid email.
    # All tests should return a tuple (bool, str) tuple. The bool indicates success (true/false), while the message str
    # indicates in plain text the reason why the test failed. If the test successfully passes sucess, the return str
    # should be empty.
    # ---------------------------------------------------------------------------------------------------------------- #

    # ------------ EDMO -------- #
    def edmo_code(self, value, args):
        if type(value) == str:
            rich.print("[yellow]WARNING: EDMO code should be integer! converting from string to int")
            try:
                value = int(value)
            except ValueError:
                return False, f"'{value}' is not a valid EDMO code"
        if value in self.metadata.edmo_codes["code"].values:
            return True, ""
        return False, f"'{value}' is not a valid EDMO code"

    def edmo_uri(self, value, args):
        if type(value) != str:
            return False, "EDMO URI should be a string"

        uri = value.replace("http", "https")  # make sure to use http
        if uri.endswith("/"):
            uri = uri[:-1]  # remove ending /


        if value in self.metadata.edmo_codes["uri"].values:
            return True, ""

        return False, f"'{value}' is not a valid EDMO code"

    # -------- SeaDataNet -------- #
    def sdn_vocab_urn(self, value, args):
        """
        Tests that the value is a valid URN for a specific SeaDataNet Vocabulary. the vocab should be specified in *args
        """
        if len(args) != 1:
            raise SyntaxError("Vocabulary identifier should be passed in args, e.g. 'P01'")
        vocab = args[0]

        if vocab not in self.metadata.sdn_vocabs_ids.keys():
            raise ValueError(
                f"Vocabulary '{vocab}' not loaded! Loaded vocabs are {self.metadata.sdn_vocabs_ids.keys()}")

        if value in self.metadata.sdn_vocabs_ids[vocab]:
            return True, ""

        return False, f"Not a valid '{vocab}' URN"

    def sdn_vocab_pref_label(self, value, args):
        """
        Tests that the value is a valid prefered label for a SeaDataNet Vocabulary. the vocab should be specified in
        *args
        """
        if len(args) != 1:
            raise SyntaxError("Vocabulary identifier should be passed in args, e.g. 'P01'")
        vocab = args[0]
        if vocab not in self.metadata.sdn_vocabs_pref_label.keys():
            raise ValueError(
                f"Vocabulary '{vocab}' not loaded! Loaded vocabs are {self.metadata.sdn_vocabs_pref_label.keys()}")

        if value in self.metadata.sdn_vocabs_pref_label[vocab]:
            return True, ""

        return False, f"Not a valid '{vocab}' prefered label"

    def cf_standard_name(self, value, args):
        """
        Tests that the value is a valid prefered label for a SeaDataNet Vocabulary. the vocab should be specified in
        *args
        """
        vocab = "P07"
        if vocab not in self.metadata.sdn_vocabs_pref_label.keys():
            raise ValueError(
                f"Vocabulary '{vocab}' not loaded! Loaded vocabs are {self.metadata.sdn_vocabs_pref_label.keys()}")

        if value in self.metadata.sdn_vocabs_pref_label[vocab]:
            return True, ""
        return False, f"Not a valid '{vocab}' prefered label"

    def sdn_vocab_uri(self, value, args):
        """
        Tests that the value is a valid URI for a SeaDataNet Vocabulary. the vocab should be specified in
        *args
        """
        if len(args) != 1:
            raise SyntaxError("Vocabulary identifier should be passed in args, e.g. 'P01'")
        vocab = args[0]

        uri = value.replace("https", "http")  # make sure to use http

        if not uri.endswith("/"):
            uri += "/"  # make sure that the uri ends with /

        if vocab not in self.metadata.sdn_vocabs_uris.keys():
            raise ValueError(
                f"Vocabulary '{vocab}' not loaded! Loaded vocabs are {self.metadata.sdn_vocabs_uris.keys()}")

        if uri in self.metadata.sdn_vocabs_uris[vocab]:
            return True, ""

        return False, f"Not a valid '{vocab}' URI"

    # --------- OceanSITES -------- #
    def oceansites_sensor_mount(self, value, args):
        if value in self.metadata.oceansites_sensor_mount:
            return True, ""
        return False, f"Sensor mount not valid, valid values are {self.metadata.oceansites_sensor_mount}"

    def oceansites_sensor_orientation(self, value, args):
        if value in self.metadata.oceansites_sensor_orientation:
            return True, ""
        return False, f"Sensor orientation not valid, valid values are {self.metadata.oceansites_sensor_orientation}"

    def oceansites_data_type(self, value, args):
        if value in self.metadata.oceansites_data_types:
            return True, ""
        return False, f"Data type not valid, valid values are {self.metadata.oceansites_data_types}"

    def oceansites_data_mode(self, value, args):
        if value in self.metadata.oceansites_data_modes:
            return True, ""
        return False, f"Data mode not valid, valid values are {self.metadata.oceansites_data_modes}"

    # -------- EMSO Data -------- #
    def emso_facility(self, value, args):
        if value in self.metadata.emso_regional_facilities:
            return True, ""
        return False, f"not a valid EMSO Regional Facility"

    def emso_site_code(self, value, args):
        if value in self.metadata.emso_sites:
            return True, ""
        return False, f"not a valid EMSO site"

    # -------- SPDX Licenses -------- #
    def spdx_license_name(self, value, args):
        if value in self.metadata.spdx_license_names:
            return True, ""
        return False, "Not a valid SPDX license code"

    def spdx_license_uri(self, value, args):
        value = value.replace("http://", "https://")  # ensure https
        value = value.replace(".jsonld", "").replace(".json", "").replace(".html", "")  # delete format
        if value in self.metadata.spdx_license_uris.values():
            return True, ""
        return False, f"Not a valid SDPX license uri '{value}'"

    # -------- Geospatial Coordinates -------- #
    def coordinate(self, value, args) -> (bool, str):
        """
        Checks if a coordinate is valid. Within args a single string indicating "latitude" "longitude" or "depth" must
        be passed
        """
        __cordinate_types = ["latitude", "longitude", "depth"]
        if len(args) != 1:
            raise SyntaxError("Coordinate type should be passed in args, e.g. 'P01'")

        coordinate = args[0].lower()  # force lowercase
        if coordinate not in __cordinate_types:
            raise SyntaxError(f"Coordinate type should be 'latitude', 'longitude' or 'depth'")
        try:
            value = float(value)
        except ValueError:
            return False, f"Could not convert '{value}' to float"

        if coordinate == "latitude" and (value < -90 or value > 90):
            return False, "latitude should be between -90 and +90"
        elif coordinate == "longitude" and (value < -180 or value > 180):
            return False, "longitude should be between -90 and +90"
        # depth is valid from a 2km tall mountain to the depths of the mariana trench
        elif coordinate == "depth" and (value < -2000 or value > 11000):
            return False, "depth should be between -2000 and 11000 metres"

        return True, ""

    # --------- Other tests -------- #
    def equals(self, value, args):
        if value == args[0]:
            return True, ""
        return False, f"expected value {args[0]}"

    def data_type(self, value, args) -> (bool, str):
        """
        Check if value is of the exepcted type.
        :param value: value to be tested
        :param args: list with one value containing a string of the type, like ['string'] or ['float']
        :returns: passed, error message
        """
        if len(args) != 1:
            raise ValueError("Expected exacly one extra argument with type")
        data_type = args[0]

        if data_type in ["str", "string"]:
            # check string
            if type(value) != str:
                return False, "not a string"

        elif data_type in ["int", "integer", "unsigned"]:
            # check string
            if type(value) != int:
                return False, "not an integer"

        elif data_type in ["float", "double"]:
            # check string
            if type(value) != float:
                return False, "not a float"

        elif data_type in ["date"]:
            return False, "unimplemented"

        elif data_type in ["datetime"]:
            try:
                pd.Timestamp(value)
            except ValueError:
                return False, "Datetime not valid, expecting format 'YYY-dd-mmTHH:MM:SS+tz'"
        else:
            raise ValueError(f"Unrecodgnized data type '{data_type}'...")

        return True, ""

    def email(self, value, args) -> (bool, str):
        if len(value) > 7:
            if re.match("^.+@(\[?)[a-zA-Z0-9-.]+.([a-zA-Z]{2,3}|[0-9]{1,3})(]?)$", value):
                return True, ""
        return False, f"email '{value}' not valid"

    def valid_doi(self, value, args) -> (bool, str):
        if re.match(r"^10.\d{4,9}/[-._;()/:A-Za-z0-9]+$", value):
            return True, ""
        return False, f"DOI '{value}' not valid"

    def check_variable_name(self, value, args) -> (bool, str):
        """
        Checks if a variable name exists in:
            1. OceanSITES
            2. P02
            3. Copernicus Params

        If not throw a warning
        """
        if value in self.metadata.oceansites_param_codes:
            return True, "Variable name found in OceanSITES"
        elif value in self.metadata.sdn_p02_names:
            return True, "Variable name found in P02"
        elif value in self.metadata.copernicus_variables:
            return True, "Variable name found in Copernicus INSTAC codes"
        else:
            return False, "Parameter name not found in OceanSITES, P02 and Copernicus!"

