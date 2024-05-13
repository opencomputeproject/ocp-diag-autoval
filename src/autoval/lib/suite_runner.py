#!/usr/bin/env python3
import copy
import getpass
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict

import yaml
from autoval.lib.utils.autoval_exceptions import CLIException
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.file_actions import FileActions
from autoval.lib.utils.site_utils import SiteUtils
from autoval.plugins.plugin_manager import PluginManager


class SuiteRunner:
    def __init__(self, autoval_cli, control_server_temp_dir) -> None:
        self.autoval_cli = autoval_cli
        self.suite_logs = self.create_suite_log_path()
        self.suite_results = {"pass": 0, "fail": 0}
        self.configurator = self.autoval_cli.configurator
        self.control_server_temp_dir = control_server_temp_dir

    def run_suite(self, suite_file) -> None:
        suite = self.get_test_suite(suite_file)
        self.suite_results = {"pass": 0, "fail": 0}
        for i, test in enumerate(suite):
            cmd = test["cmd"]
            params = test.get("args", None)
            AutovalLog.log_info("Running test {}/{}: {}".format(i + 1, len(suite), cmd))
            test_passed = self.run_test(cmd, params)
            if not test_passed and not test.get("continue_on_fail", False):
                AutovalLog.log_info("continue_on_fail not set, stopping suite")
                break
        AutovalLog.log_info(
            "Suite completed.\nPassed Tests: {}\nFailed Tests: {}".format(
                self.suite_results["pass"], self.suite_results["fail"]
            )
        )

    def get_test_suite(self, suite_file: str):
        if not self.configurator:
            try:
                with open(suite_file) as fh:
                    return yaml.load(fh, Loader=yaml.FullLoader)
            except Exception as e:
                raise CLIException(
                    "Failed to load suite file {}: {}".format(suite_file, str(e))
                )
        else:
            return yaml.load(
                PluginManager.get_plugin_cls(
                    "config_datasource"
                )().read_config_as_string(suite_file),
                Loader=yaml.FullLoader,
            )

    def run_test(self, test, args) -> bool:
        _test_start_time = time.time()
        _date = datetime.fromtimestamp(_test_start_time).strftime("%Y-%m-%d_%H-%M-%S")
        log_path: str = os.path.join(self.suite_logs, f"{test}_{_date}")
        self.autoval_cli.config["logdir"] = log_path
        FileActions.mkdirs(log_path)

        autoval_runner = os.path.abspath(sys.argv[0])
        # -c option for host config file, -t to use Thrift
        exec_cmd = [
            autoval_runner,
            test,
        ]
        if self.autoval_cli.config:
            remote_config = copy.deepcopy(self.autoval_cli.config)
            remote_config["logdir"] = log_path
            remote_cfg_path = self.generate_remote_cfg(remote_config)
            exec_cmd.extend(["-c", remote_cfg_path])
        else:
            raise CLIException("No config provided to continue test")

        # @@@ TODO: Support other command line parameters such as --debug
        debug_log = self._get_test_log_file(test, _date)
        test_control = self.generate_test_control(args, log_path)
        AutovalLog.log_info(f"Log location {log_path}")
        AutovalLog.log_info(f"Temporary Debug log:  {debug_log}")

        if test_control:
            exec_cmd.extend(["--test_control", test_control])
        if args and args.get("thrift", False):
            exec_cmd.append("-t")

        # get control server tmp dir to store data locally.
        debug_log_path = os.path.join(self.control_server_temp_dir, debug_log)

        with open(debug_log_path, "a") as logfile:
            process = subprocess.Popen(exec_cmd, stdout=logfile, stderr=logfile)
            process.communicate()
            ret_code = process.returncode

        # Backp the logs to Manifold
        FileActions.copy_from_local(
            None, debug_log_path, os.path.join(log_path, debug_log)
        )
        FileActions.rm(debug_log_path)

        if ret_code:
            result = "FAIL"
            self.suite_results["fail"] = self.suite_results["fail"] + 1
        else:
            result = "PASS"
            self.suite_results["pass"] = self.suite_results["pass"] + 1

        AutovalLog.log_info("Test {} finished. Result: {}".format(test, result))
        return result == "PASS"

    def create_suite_log_path(self) -> str:
        if self.autoval_cli.config.get("logdir", False):
            dir_path = self.autoval_cli.config["logdir"]
        else:
            dir_path = SiteUtils.get_site_setting("resultsdir")

        suite_start_time = time.time()
        _date = datetime.fromtimestamp(suite_start_time).strftime("%Y-%m-%d_%H-%M-%S")
        _user = getpass.getuser()
        dir_path = os.path.join(dir_path, "suite_logs", _user, _date)
        FileActions.mkdirs(dir_path)
        return dir_path

    def _get_test_log_file(self, test, _date):
        test_log = f"{test}.{_date}.DEBUG"
        test_log_path = os.path.join(test_log)
        return test_log_path

    def generate_test_control(self, args: Dict, log_dir: str) -> str:
        test_control = ""
        if args and args.get("test_params", False):
            test_control = os.path.join(log_dir, "test_control.json")
            FileActions.write_data(
                test_control, "{}".format(json.dumps(args["test_params"]))
            )
        return test_control

    def generate_remote_cfg(self, remote_config: Dict) -> str:
        test_remote_cfg = os.path.join(remote_config["logdir"], "remote_cfg.json")
        FileActions.write_data(
            test_remote_cfg, "{}".format(json.dumps(self.autoval_cli.config))
        )
        return test_remote_cfg
