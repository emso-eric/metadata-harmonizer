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
from . import EmsoMetadata, init_emso_metadata
from .utils import group_metadata_variables, check_url
import inspect
import numpy as np
from dataclasses import dataclass
from urllib.parse import urlparse

@dataclass
class Context:
    metadata: dict  # All the metadata
    section: str    # section, like "coordinates" or "global"
    varname: str  # variable under test, used "global" for global attributes


class EmsoMetadataTester:
    def __init__(self, specifications=""):
        """
        This class implements the tests to ensure that the metadata in a particular ERDDAP is harmonized with the EMSO
        metadata standards. The tests are configured in the 'EMSO_Metadata_Specifications.md' document. There should be 2 different
        tables with the tests defined, one for the global attributes and another one for tests to be carreid
        """
        # Dict to store all erddap. KEY is the test identifier while value is the method
        rich.print("[blue]Setting up EMSO Metadata Tests...")

        self.metadata = init_emso_metadata(force_update=True, specifications=specifications)
        self.context = None  # here info about the current attribute being tested will be stored

        self.implemented_tests = {}
        for name, element in inspect.getmembers(self):
            if name == "validate_dataset":  # exclude validate dataset from tests
                continue
            # Assume that all methods not starting with "_" are tests!
            elif inspect.ismethod(element) and not name.startswith("_"):
                self.implemented_tests[name] = element

        rich.print(f"Currently there are {len(self.implemented_tests)} tests implemented")

        # ensure that all required test are implemented...
        all_tests = self.metadata.global_attr["Compliance test"].to_list()
        all_tests += self.metadata.cor_variables_attr["Compliance test"].to_list()
        all_tests += self.metadata.env_variables_attr["Compliance test"].to_list()
        all_tests += self.metadata.bio_variables_attr["Compliance test"].to_list()
        all_tests += self.metadata.qc_variables_attr["Compliance test"].to_list()
        all_tests += self.metadata.sensor_variables_attr["Compliance test"].to_list()
        all_tests += self.metadata.platform_variables_attr["Compliance test"].to_list()

        all_tests = [value.split("#")[0] for value in all_tests]
        all_tests = np.unique(all_tests)
        error = False
        for test in all_tests:
            if test not in self.implemented_tests.keys():
                rich.print(f"[red]ERROR test {test} not implemented!")
                error = True
        if error:
            pass # TODO implement tests and uncoment exception
            # raise ValueError("Some tests are not implemented")

        # valid discrete sampling geometries from the Climate and Forecast conventions, more info at:
        # https://cfconventions.org/cf-conventions/cf-conventions.html#discrete-sampling-geometries
        self.valid_cf_dsg_types = ["point", "timeSeries", "trajectory", "profile", "timeSeriesProfile",
                                   "trajectoryProfile"]



    def __process_results(self, df, verbose=False, ignore_ok=False) -> (float, float, float):
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

            if row["passed"] and row["message"] != "not defined" and ignore_ok:
                continue
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

    def run_test(self, context: Context, test_name: str, args: list, attribute: str, required: bool, multiple: bool,
                   annotation: int, results: dict) -> (bool, str, any):
        """
        Applies the method test to the dict data and stores the output into results
        :param context: Context object
        :param test_name: name of the test to apply
        :param args: arguments of the test (from the specs)
        :param attribute: NetCDF / ERDDAP attribute being tested
        :param required: is the argument mandatory (True) of optional (False)
        :param multiple: Can the test accept multiple arguments?
        :param annotation: Annotation in the table, marked as <sup>1</sup>, may indicate special behaviour (like separate by comma)
        :param results: dict to store the results
        """
        assert isinstance(context, Context)
        assert isinstance(test_name, str)
        assert isinstance(args, list)
        assert isinstance(attribute, str)
        assert isinstance(required, bool)
        assert isinstance(multiple, bool)
        assert isinstance(annotation, int)
        assert isinstance(results, dict)

        implemented = False
        self.context = context
        metadata = context.metadata[context.section][context.varname]

        if attribute in metadata.keys():
            if test_name not in self.implemented_tests.keys():
                rich.print(f"[red]Test '{test_name}' not implemented!")

            else:
                implemented = True

            value = metadata[attribute]


            def split_variable(str_value, separator):
                if isinstance(str_value, np.ndarray) or isinstance(str_value, list):
                    str_value = separator.join([str(a) for a in str_value])

                value_list = str_value.split(separator)  # split multiple values
                return [a.strip() for a in value_list]

            if multiple:
                if annotation == 1:  # Annotation 1 means use comma to separate
                    values = split_variable(value, ",")
                else:  # By default, separate by space
                    values = split_variable(value, " ")
            else:
                values = [value]

            if not implemented:
                passed = False
                message = f"unimplemented"

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

        elif self.__check_exceptions(context, attribute):
            passed = True
            message = "not required (exception)"
            value = ""

        elif annotation == 7 and context.varname != "platform_id":
            # Annotation 7 means that only platform_id requires cf_role
            passed = True
            message = "not required"
            value = ""
        else:
            passed = False
            message = "not found"
            value = ""

        results["attribute"].append(attribute)
        results["variable"].append(context.varname)
        results["passed"].append(passed)
        results["required"].append(required)
        results["message"].append(message)
        results["value"].append(value)
        return passed, message, value

    def __check_exceptions(self, context: Context, attribute: str):
        exceptions = {
            "sensor_id": ["sdn_uom_uri", "sdn_uom_urn", "sdn_uom_name", "units", "standard_name"],
            "platform_id": ["sdn_uom_uri", "sdn_uom_urn", "sdn_uom_name", "units"]
        }
        for exc_varname, exc_attributes in exceptions.items():
            if context.varname == exc_varname and attribute in exc_attributes:
                return True
        return False

    def __test_group_handler(self, test_group: pd.DataFrame, metadata: dict, section: str, varname: str, verbose: bool,
                             results={}) -> dict:
        """
        Takes a list of tests from the metadata specification and applies it to the metadata json structure
        :param test_group: DataFrame of the group of tests required
        :param metadata: JSON structure (dict) under test
        :param varname: Variable name being tested, 'global' for global dataset attributes
        :param verbose: if True, will add attributes present in the dataset but not required by the standard.
        :param results: a dict to store the results. If empty a new one will be created
        :returns: result structure
        """
        assert isinstance(test_group, pd.DataFrame)
        assert isinstance(metadata, dict)
        assert isinstance(varname, str)
        assert isinstance(verbose, bool)
        assert isinstance(results, dict), f"Expected dict got {type(results)}"
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
            annotation = row["annotations"]
            if not test_name:
                rich.print(f"[yellow]WARNING: test for {attribute} not implemented!")
                continue

            args = []

            if "#" in test_name:
                test_name, args = test_name.split("#")
                args = args.split(",")  # comma-separated fields are args

            context = Context(metadata, section, varname)
            self.run_test(context, test_name, args, attribute, required, multiple, annotation, results)

        if verbose:  # add all parameters not listed in the standard
            checks = list(test_group[attribute_col].values)
            for key, value in metadata[section][varname].items():
                if key not in checks:
                    results["attribute"].append(key)
                    results["variable"].append(varname)
                    results["passed"].append("n/a")
                    results["required"].append("n/a")
                    results["message"].append("not defined")
                    if type(value) == str and len(value) > 100:
                        value = value.strip()[:60] + "..."
                    results["value"].append(value)
        return results

    def validate_dataset(self, metadata, verbose=True, variable_filter=[], ignore_ok=False):
        """
        Takes the well-formatted JSON metadata from an ERDDAP dataset and processes it
        :param metadata: well-formatted JSON metadta for an ERDDAP dataset
        :return: a DataFrame with the following columns: [attribute, variable, required, passed, message, value]
        """
        metadata = group_metadata_variables(metadata)
        # Try to get a dataset id
        global_attr = metadata["global"]["global"]
        if "dataset_id" in global_attr.keys():
            dataset_id = global_attr["dataset_id"]
        elif "id" in global_attr.keys():
            dataset_id = global_attr["id"]
        else:
            dataset_id = global_attr["title"]

        rich.print(f"#### Validating dataset [cyan]{global_attr['title']}[/cyan] ####")

        # Test global attributes
        if "global" in variable_filter or not variable_filter:
            results = self.__test_group_handler(self.metadata.global_attr, metadata, "global", "global", verbose)
        else:
            results = {}

        test_mapping = (
            # variable group, list of tests
            ("coordinate", self.metadata.cor_variables_attr),
            ("environmental", self.metadata.env_variables_attr),
            ("biological", self.metadata.bio_variables_attr),
            ("technical", self.metadata.tec_variables_attr),
            ("quality_control", self.metadata.qc_variables_attr),
            ("sensor", self.metadata.sensor_variables_attr),
            ("platform", self.metadata.platform_variables_attr),

            # Test unclassified as environmental
            ("unclassified", self.metadata.env_variables_attr),

        )
        for section, attributes in test_mapping:
            group = metadata[section]
            for varname in group.keys():
                if variable_filter and varname not in variable_filter:
                    continue
                results = self.__test_group_handler(attributes, metadata, section, varname, verbose, results)

        df = pd.DataFrame(results)
        total, required, optional = self.__process_results(df, verbose=verbose, ignore_ok=ignore_ok)
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

        return False, f"Not a valid '{vocab}' preferred label"

    def sdn_vocab_alt_label(self, value, args):
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

        if value in self.metadata.sdn_vocabs_alt_label[vocab]:
            return True, ""

        return False, f"Not a valid '{vocab}' alternative label"

    def cf_standard_name(self, value, args):
        """
        Tests that the value is a valid prefered label for a SeaDataNet Vocabulary. the vocab should be specified in
        *args
        """
        if self.context.varname == "sensor_id":
            return True, "not CF name for sensor_id, ignore it"

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

        if isinstance(value, list):
            value = " ".join([str(v) for v in value])

        if value == args[0]:
            return True, ""
        return False, f"expected value '{args[0]}'"

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

        if isinstance(value, list) and data_type in ["str", "string"]:
            value = " ".join([str(v) for v in value])

        if data_type in ["str", "string"]:
            # check string
            if type(value) != str:
                return False, "not a string"

        elif data_type in ["int", "integer", "unsigned"]:
            # check string
            if type(value) != int:
                try:
                    int(value)
                except ValueError:
                    return False, "not a float"


        elif data_type in ["float", "double"]:
            # check string
            if type(value) != float:
                try:
                    float(value)
                except ValueError:
                    return False, "not a float"

        elif data_type in ["url", "uri"]:
            try:
                result = urlparse(value)
            except ValueError:
                return False
            if not value.startswith("http"):
                return False, "URL does not start with http"

        elif data_type in ["date"]:
            return False, "unimplemented"

        elif data_type in ["datetime"]:
            try:
                pd.Timestamp(value)
            except ValueError:
                return False, "Datetime not valid, expecting format 'YYY-dd-mmTHH:MM:SS+tz'"
        else:
            raise ValueError(f"Unrecognized data type '{data_type}'...")

        return True, ""

    def email(self, value, args) -> (bool, str):
        if len(value) > 7:
            if re.match(r"^.+@(\[?)[a-zA-Z0-9-.]+.([a-zA-Z]{2,3}|[0-9]{1,3})(]?)$", value):
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

    def is_coordinate(self, value, args):
        valid_coordinates = ["time", "depth", "latitude", "longitude", "sensor_id", "platform_id", "precise_latitude",
                             "precise_longitude"]
        if value in valid_coordinates:
            return True, ""
        else:
            return False, "coordinate name not valid"

    #----- Quality control stuff -----#
    def qc_flag_values(self, value, args):
        expected_values = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
        if "," in value:
            # ERDDAP sometimes adds comma to arrays, just ignore it
            value = value.replace(",", "")

        if value in expected_values:
            return True, ""
        else:
            return False, f"Unexpected value '{value}'"


    def qc_flag_meanings(self, value, args):
        expected_values = ["unknown", "good_data", "probably_good_data", "potentially_correctable_bad_data",
                           "bad_data", "nominal_value", "interpolated_value", "missing_value"]
        if value in expected_values:
            return True, ""
        else:
            return False, f"Unexpected value '{value}'"

    def qc_variable_name(self,value, args):

        # Create a list with ALL ancillary variables listed
        ancillary_vars = []
        for section in self.context.metadata.keys():
            if section == "global":
                continue
            for varname, v in self.context.metadata[section].items():
                if v["variable_type"] == "quality_control": # it should not be possible to have TEMP_QC_QC
                    continue
                if "ancillary_variables" in v.keys():
                    ancillary_vars += v["ancillary_variables"].split(" ")

        if not self.context.varname.endswith("_QC"):
            return False, "expected varname ending with _QC"
        elif self.context.varname not in ancillary_vars:
            return False, "Quality Control not declared in any variable!"

        return True, ""

    #------ Climate and Forecast Discrete Sampling Geometry -------#
    def cf_dsg_types(self, value, args):
        # ERDDAP modifies CF DSG types by changing the first char to upper case
        cf_dsg_types_erddap = [a[0].upper() + a[1:] for a in self.valid_cf_dsg_types]

        if value in self.valid_cf_dsg_types:
            return True, ""
        elif value in cf_dsg_types_erddap:
            return True, ""
        else:
            return False, "Not a valid CF Discrete Sampling Geometry"

    #------ Darwin Core Terms ----#
    def dwc_term_name(self, value, args):
        if value in self.metadata.dwc_terms["name"].to_list():
            return True, ""
        else:
            return False, "Not a valid Darwin Core term name"

    def dwc_term_uri(self, value, args):
        if value in self.metadata.dwc_terms["uri"].to_list():
            return True, ""
        else:
            return False, "Not a valid Darwin Core term uri"

    #-------- ROR registry --------#
    def ror_uri(self, value, args):
        # try to get the value from the ROR registry, like https://ror.org/03mb6wj31
        if not value.startswith("https://ror.org/"):
            return False, "Not a valid ROR URI"

        if not check_url(value):
            return False, "URL not reachable"

        return True, ""

    def oso_ontology_name(self, value, args):
        oso_type = args[0]
        assert oso_type in ["rf", "site", "platform"]

        if oso_type == "rf" :
            if not self.metadata.oso.check_rf(value, "label"):
                return False, "RF not found in OSO"

        elif oso_type == "site":
            if not self.metadata.oso.check_site(value, "label"):
                return False, "Site not found in OSO"

        elif oso_type == "platform":
            if not self.metadata.oso.check_platform(value, "label"):
                return False, "Platform not found in OSO"
        else:
            raise ValueError(f"Unimplemented oso_type {oso_type}")

        return True, ""

    def oso_ontology_uri(self, value, args):
        oso_type = args[0]
        assert oso_type in ["rf", "site", "platform"]

        if oso_type == "rf":
            if not self.metadata.oso.check_rf(value, "uri"):
                return False, "RF not found in OSO"

        elif oso_type == "site":
            if not self.metadata.oso.check_site(value, "uri"):
                return False, "Site not found in OSO"

        elif oso_type == "platform":
            if not self.metadata.oso.check_platform(value, "uri"):
                return False, "Platform not found in OSO"
        else:
            raise ValueError(f"Unimplemented oso_type {oso_type}")

        return True, ""

    def contributor_types(self, value, args):
        if value in self.metadata.datacite_contributor_roles:
            return True, ""

        return False, f"role '{value}' not valid!!"
