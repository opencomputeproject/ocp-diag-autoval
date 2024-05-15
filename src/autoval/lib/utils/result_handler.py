#!/usr/bin/env python3

import json
import os

from autoval.lib.test_args import TestArgs
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.autoval_output import AutovalOutput as autoval_output
from autoval.lib.utils.generic_utils import GenericUtils
from autoval.lib.utils.manifest import Manifest


class ResultHandler:
    # pyre-fixme[4]: Attribute must be annotated.
    test_results = {}  # referenced by file_actions so can't remove
    # pyre-fixme[4]: Attribute must be annotated.
    cmd_metrics = []  # referenced by test_autoval_log so can't remove
    # pyre-fixme[4]: Attribute must be annotated.
    test_steps = []

    # pyre-fixme[2]: Parameter must be annotated.
    def __init__(self, test=None) -> None:
        # pyre-fixme[4]: Attribute must be annotated.
        self.test = test
        self.results_dir = ""
        # pyre-fixme[4]: Attribute must be annotated.
        self.test_summary = {}
        # pyre-fixme[4]: Attribute must be annotated.
        self.failed_steps = None
        # pyre-fixme[4]: Attribute must be annotated.
        self.warning_steps = None
        # pyre-fixme[4]: Attribute must be annotated.
        self.passed_steps = None
        # pyre-fixme[4]: Attribute must be annotated.
        self.test_params = None

    def add_results_dir(self, dir: str) -> None:
        """
        Add the results directory path
        Args:
            dir (string): Results directory path
        """
        self.results_dir = dir

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def _get_test_results_file_path(self, file_name):
        file_path = os.path.join(self.results_dir, "%s" % file_name)
        return file_path

    def save_test_results(self) -> None:
        """
        Save test results to various output files
        """
        manifest = Manifest().get_test_manifest()
        self.add_test_results(manifest)
        test_summary = self.create_test_summary()
        self.add_test_results({"test_summary": test_summary})
        file_path = self._get_test_results_file_path("test_results.json")
        AutovalLog.log_info(f"saving results at {file_path}")
        self.save_results(file_path)
        file_path = self._get_test_results_file_path("test_steps.json")
        self.save_steps(file_path)
        summary_file_path = self._get_test_results_file_path("test_summary.json")
        self.save_test_summary_results(summary_file_path)

    def print_test_summary(self) -> None:
        """
        Print the test summary details at the end of a test
        """
        from autoval.lib.utils.autoval_utils import AutovalUtils

        failed = AutovalUtils.get_failed_test_steps()
        warning = AutovalUtils.get_warning_steps()
        passed = AutovalUtils.get_passed_test_steps()
        failed_str = ""
        if failed:
            failed_str = " (Step Number {})".format(
                ", ".join(str(step) for step in failed)
            )
        test_summary = self.create_test_summary()

        AutovalLog.log_info(
            "+++Test Finished:\nTest Summary: {}\nPassed Steps: {}\nWarning Steps: {}\nFailed Steps: {}{}"
            "\nTest Result : {}".format(
                test_summary,
                len(passed),
                len(warning),
                len(failed),
                failed_str,
                str(self.test.test_status.value),
            )
        )

    # pyre-fixme[2]: Parameter must be annotated.
    def add_test_results(self, results) -> None:
        """
        Updates the self.test_results dictionary with additional
        results that will later be saved
        @param: Dictionary of key / value test results to store
        """
        self.test_results.update(results)
        str_results = json.dumps(results)
        autoval_output.add_measurement("test-results", str_results)

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def add_test_summary_results(self, results):
        """
        Updates the self.test_summary dictionary with additional
        results that will later be saved
        @param: Dictionary of key / value lab results to store
        """
        self.test_summary.update(results)

    # pyre-fixme[2]: Parameter must be annotated.
    def update_test_results(self, results) -> None:
        """
        Updates the self.test_results dictionary with additional
        results as list n the given key
        @param: Dictionary of key / value test results to store
        """
        for key, value in results.items():
            if isinstance(value, list):
                if key not in self.test_results:
                    self.test_results[key] = []
                self.test_results[key].extend(value)
            elif isinstance(value, dict):
                if key not in self.test_results:
                    self.test_results[key] = {}
                self.test_results[key].update(value)

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def update_test_summary_results(self, results):
        """
        Updates the self.test_summary dictionary with additional
        results as list n the given key
        @param: Dictionary of key / value test results to store
        """
        for key, value in results.items():
            if isinstance(value, list):
                if key not in self.test_summary:
                    self.test_summary[key] = []
                self.test_summary[key].extend(value)
            elif isinstance(value, dict):
                if key not in self.test_summary:
                    self.test_summary[key] = {}
                self.test_summary[key].update(value)

    # pyre-fixme[2]: Parameter must be annotated.
    def add_test_step(self, step_data) -> None:
        self.test_steps.append(step_data)

    def save_results(self, file_path: str) -> None:
        """
        Saves everything that was added using 'add_test_results' in a JSON
        file
        @param file_path: Path where to save JSON file
        """
        if self.test_results:
            self.test_results = GenericUtils.convert_to_ascii(self.test_results)
            self._save_json(self.test_results, file_path)

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def save_test_summary_results(self, file_path):
        """
        Saves everything that was added using 'add_test_summary_results' in a JSON
        file
        @param file_path: Path where to save JSON file
        """
        if self.test_summary:
            AutovalLog.log_info("saving test_summary results at %s" % (file_path))
            self.test_summary = GenericUtils.convert_to_ascii(self.test_summary)
            self._save_lab_json(self.test_summary, file_path)

    def save_steps(self, file_path: str) -> None:
        """
        Save the test steps to the steps file

        Args:
            file_path (string): The path to the steps file
        """
        if self.test_steps:
            AutovalLog.log_info("saving test steps at %s" % (file_path))
            self.test_steps = GenericUtils.convert_to_ascii(self.test_steps)
            self._save_json(self.test_steps, file_path)

    def create_test_summary(self) -> str:
        """
        Creates the test summary using the doc string of the test class
        Returns:
            str: the test summary
        """
        test_params = None
        try:
            test_params = self.test.get_test_params()
        except Exception as ex:
            AutovalLog.log_info("Failed to create Test Summary. err - {}".format(ex))
        test_summary = self.test.test_name
        if hasattr(self.test, "_doc"):
            if self.test._doc:
                test_summary += " " + self.test._doc  # noqa
            if test_params:
                test_summary += " Parameters: " + test_params  # noqa
        else:
            AutovalLog.log_info("Missing doc string in {}".format(self.test.test_name))
        return test_summary

    @classmethod
    def _save_json(cls, data: str, file_path: str) -> None:
        from autoval.lib.utils.file_actions import FileActions

        FileActions.write_data(file_path, data)

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def _save_lab_json(cls, data, file_path) -> None:
        """
        Storing the lab outputs without sorting into the
        lab output json file
        """
        with open(file_path, "w") as fp:
            json.dump(data, fp, indent=4)
            fp.flush()
            os.fsync(fp)

    @classmethod
    def add_cmd_metric(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        cmd,
        # pyre-fixme[2]: Parameter must be annotated.
        start_time,
        # pyre-fixme[2]: Parameter must be annotated.
        duration,
        # pyre-fixme[2]: Parameter must be annotated.
        exit_code,
        # pyre-fixme[2]: Parameter must be annotated.
        output,
        # pyre-fixme[2]: Parameter must be annotated.
        hostname=None,
    ) -> None:
        """
        TODO:

        Args:
            cmd (string): [description]
            start_time (int): [description]
            duration (int): [description]
            exit_code (int): [description]
            output ([type]): [description]
            hostname ([type], optional): [description]. Defaults to None.
        """

        if not TestArgs().collect_cmd_metrics:
            # Collecting cmd metrics was disabled through test control file
            return

        cmd_dict = {
            "command": cmd,
            "start_time_ms": int(start_time * 1000),
            "duration_ms": int(duration * 1000),
            "exit_code": exit_code,
            "output": output,
        }
        if hostname:
            cmd_dict["target_hostname"] = hostname
        cls.cmd_metrics.append(cmd_dict)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_cmd_metrics(cls):
        """
        Deprecated class method
        """
        return cls.cmd_metrics

    @classmethod
    def save_cmd_metrics(cls, file_path: str) -> None:
        """
        Deprecated class method
        """
        if cls.cmd_metrics:
            AutovalLog.log_info("saving cmd metrics at %s" % (file_path))
            cls.cmd_metrics = GenericUtils.convert_to_ascii(cls.cmd_metrics)
            cls._save_json(cls.cmd_metrics, file_path)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def save_result_threshold_data(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        raw_result=None,
        # pyre-fixme[2]: Parameter must be annotated.
        metric_result=None,
        # pyre-fixme[2]: Parameter must be annotated.
        metric_threshold=None,
    ):

        thresholds = {}
        if metric_threshold:
            for metric, threshold_obj in metric_threshold.items():
                thresholds[metric] = {
                    k: v
                    for k, v in dict(threshold_obj).items()
                    if k
                    in [
                        "value",
                        "comparison",
                        "unit",
                        "configerator_rule_name",
                        "formula",
                    ]
                }

        return {
            "metrics": {
                "raw_result": raw_result,
                "metrics_results": metric_result,
                "metrics_thresholds": thresholds,
            }
        }
