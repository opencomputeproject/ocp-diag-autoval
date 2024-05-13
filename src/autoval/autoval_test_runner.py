#!/usr/bin/env python3

import inspect
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from shutil import rmtree

from autoval.lib.test_args import TestArgs
from autoval.lib.test_base import TestBase
from autoval.lib.utils.autoval_utils import AutovalLog
from autoval.lib.utils.file_actions import FileActions
from autoval.lib.utils.site_utils import SiteUtils
from autoval.plugins.plugin_manager import PluginManager


class AutovalLogger:
    def __init__(self, control_server_temp_dir):
        self.control_server_temp_dir = control_server_temp_dir
        self.autoval_runner_debug_log = None

    def setup(
        self,
        test_name: str,
        save_console_log: bool = False,
        debug: bool = False,
        suite: bool = False,
    ):
        _date = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d_%H-%M-%S")
        filename = (
            f"suite_console_{_date}.log" if suite else f"{test_name}_{_date}.DEBUG"
        )
        self.autoval_runner_debug_log = os.path.join(
            self.control_server_temp_dir, filename
        )

        if save_console_log:
            # redirect autoval logger log too tmp _autoval_runner_local_log file
            AutovalLog.set_logging(
                console_file_log_enabled=True,
                filename=self.autoval_runner_debug_log,
                debug=debug,
            )
        else:
            AutovalLog.set_logging(debug=debug)

    def save_logger_output(self, dest_log_path: str = None):
        # restore logging to default settings.
        AutovalLog.set_logging()

        # save logs to manifold dir
        if not dest_log_path:
            from autoval.lib.utils.site_utils import SiteUtils

            _resultsdir = SiteUtils.get_resultsdir()
            dest_file_path = (
                _resultsdir + f"/{self.autoval_runner_debug_log.split('/')[-1]}"
            )
        else:
            dest_file_path = (
                dest_log_path + "/" + os.path.basename(self.autoval_runner_debug_log)
            )
        FileActions.copy_from_local(
            host=None, local_path=self.autoval_runner_debug_log, dst_path=dest_file_path
        )
        FileActions.rm(self.autoval_runner_debug_log)


class AutoValTestRunner:
    def __init__(self, parser) -> None:
        self.test_module = parser.test_module
        self.test_class = parser.test_class
        self.suite = parser.suite
        self.dry_run = parser.dry_run
        self.function_name = parser.func_name
        self.function_args = parser.func_args
        self.run_local_code = parser.run_local_code
        self.save_console_log = parser.save_console_log
        self.debug = parser.debug
        # initialize Test args.
        self._test_args = TestArgs(parser)
        self.parser = parser
        self.control_server_temp_dir = None

    def get_control_server_tmp_dir(self):
        site_settings_details = SiteUtils.get_site_settings()
        _control_server_temp_dir = site_settings_details["control_server_tmpdir"]
        # get parent directory.
        _control_server_temp_dir = os.path.split(_control_server_temp_dir.rstrip("/"))[
            0
        ]

        # if control server tmp dir not exist, create it.
        if not os.path.exists(_control_server_temp_dir):
            os.makedirs(_control_server_temp_dir, exist_ok=True)

        return _control_server_temp_dir

    def main(self) -> None:

        self.control_server_temp_dir = self.get_control_server_tmp_dir()
        autoval_logger = AutovalLogger(self.control_server_temp_dir)
        autoval_logger.setup(
            self.test_module.split(".")[-1],
            save_console_log=self.save_console_log,
            debug=self.debug,
            suite=self.suite,
        )
        if self.suite:
            from autoval.lib.suite_runner import SuiteRunner

            s = SuiteRunner(self.parser, self.control_server_temp_dir)
            s.run_suite(self.suite)
            if self.save_console_log:
                autoval_logger.save_logger_output(dest_log_path=s.suite_logs)
            if s.suite_results["fail"] != 0:
                sys.exit(-1)
            return

        try:
            __import__(self.test_module, globals(), locals(), ["*"])
            if self.dry_run:
                print(f"Imported {self.test_module} successfully")
        except ModuleNotFoundError as e:
            print(
                f"Failed to import {self.test_module}, make sure the module"
                " exists  - " + str(e)
            )
            sys.exit(-1)
        if self.run_local_code:
            self.execute_code()
            return
        if not self.test_class:
            self.test_class = self._get_test_class(self.test_module)
        try:
            cls = getattr(sys.modules[self.test_module], self.test_class)
        except AttributeError:
            print(
                f"Failed to load {self.test_class}, make sure the class exists "
                f"in {self.test_module}"
            )
            sys.exit(-1)

        if self.dry_run:
            sys.exit(0)

        try:
            # pyre-fixme[61]: `cls` may not be initialized here.
            obj = cls()
            obj.lifecycle()
        finally:
            if self.save_console_log:
                autoval_logger.save_logger_output()

        # [aeh] Note on process exit code:
        # If any exception is raised during the test setup or teardown above,
        # the exception bubbles up the stack, left unhandled and process exits with code 1.
        # Otherwise, return a process exit code based on the test execution outcome.
        sys.exit(obj.get_return_code())

    def execute_code(self) -> None:
        if self.test_class is not None:
            try:
                _class = getattr(sys.modules[self.test_module], self.test_class)
            except AttributeError:
                raise Exception("%s class not found" % self.test_class)
        else:
            _class = sys.modules[self.test_module]
        _method = getattr(_class, self.function_name)
        tmpdir = tempfile.mkdtemp(prefix="autoval_module_runner_")
        os.chdir(tmpdir)
        if self.function_args is not None:
            data = _method(*self.function_args)
        else:
            data = _method()
        rmtree(tmpdir, ignore_errors=True)
        data_json = json.dumps(data)
        print(data_json)

    def _get_test_class(self, module_name: str) -> str:
        # Finds the classes defined in a module
        # Returns the name of the class if exactly 1 class is found
        # Prints error and exits if not exactly 1 class is found
        # import testbase here so testargs get initialized in init.

        cls_members = [
            name
            for name, _obj in inspect.getmembers(
                sys.modules[module_name],
                lambda member: inspect.isclass(member)
                and (issubclass(member, TestBase))
                and member.__module__ == module_name,
            )
        ]
        if len(cls_members) != 1:
            print(
                f"Need exactly 1 class in {module_name} to run test, found "
                f"{len(cls_members)} classes"
            )
            sys.exit(-1)
        return cls_members[0]


def main() -> None:
    autoval_cli = PluginManager.get_plugin_cls("autoval_cli")
    AutoValTestRunner(autoval_cli()).main()


if __name__ == "__main__":
    main()
