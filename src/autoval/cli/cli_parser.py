#!/usr/bin/env python3

import argparse
import json
import os
import tempfile
from ast import literal_eval
from pprint import pprint
from typing import Optional

from autoval.lib.utils.autoval_exceptions import CLIException
from autoval.lib.utils.generic_utils import GenericUtils


class AutoValCLI:
    def __init__(
        self,
        parse_only_args: bool = False,
        cli_args_prefilled: Optional[argparse.Namespace] = None,
    ) -> None:

        self.description = "AutoVal CLI"
        self.parser = None
        if cli_args_prefilled is not None:
            self.args = cli_args_prefilled
        else:
            self.args = self.parse_cli()

        if parse_only_args:
            return

        self.func_name = self.args.function_name
        self.func_args = self.args.func_args
        self.test_class = self.args.test_class
        self.debug = self.args.debug
        self.test_module = self.args.module
        self.suite = self.args.suite
        self.dry_run = self.args.dry_run
        self.run_local_code = self.args.run_local_code
        self.config = None
        self.save_console_log = self.args.save_console_log
        self.test_control = {}
        if all([self.suite, self.test_module]):
            raise CLIException("Specify either suite or module")
        # Check if invoked specific py module.
        if self.run_local_code:
            if not self.func_name:
                raise CLIException(
                    "Function name (-f/--func) is mandatory with -r/--run_local_code "
                )
            return
        if not self.debug:
            self.debug = self.test_control.get("debug", self.debug)
        self.initialize_args()
        # if dry_run is set we don't need to initialize any other
        # attributes as we just try to instantiate the module
        if self.dry_run:
            if self.test_control:
                self._extract_test_control()
            return

    def parse_cli(self) -> argparse.Namespace:

        parser = self.get_cli_parser()
        args = parser.parse_known_args()[0]
        return args

    def initialize_args(self):
        self.test_control = self._initialize_test_control()
        self.config = self._initialize_config()

    def get_cli_parser(self) -> argparse.ArgumentParser:
        self.parser = argparse.ArgumentParser(
            description=self.description, formatter_class=argparse.RawTextHelpFormatter
        )
        self.parser.add_argument(
            "module", nargs="?", default="", help="Test module to execute"
        )
        self.parser.add_argument(
            "--test_class",
            required=False,
            dest="test_class",
            help="Test class to execute",
        )
        self.parser.add_argument(
            "--config",
            "-c",
            required=False,
            dest="config",
            help="Server config specification in JSON format",
        )
        self.parser.add_argument(
            "--test_control",
            dest="test_control",
            required=False,
            help="Test control specification in JSON format",
        )
        self.parser.add_argument(
            "--debug",
            dest="debug",
            required=False,
            action="store_true",
            help="Set to enable debug output",
        )
        self.parser.add_argument(
            "--dry_run",
            dest="dry_run",
            required=False,
            action="store_true",
            help="Set to do a dry run, don't execute the test",
        )
        self.parser.add_argument(
            "--args",
            dest="cli_args",
            required=False,
            help=(
                "Custom user args that overwrite test_control settings. "
                "Examples:\n"
                'test.par --args "runtime: 3600, cycle_type: reboot"\n'
                'test.par --args \'{"runtime": 3600, "cycle_type": "reboot"}\''
            ),
        )
        self.parser.add_argument(
            "--suite",
            dest="suite",
            required=False,
            help="Test suite to run in YAML format",
        )
        self.parser.add_argument(
            "-r",
            "--run_local_code",
            action="store_true",
            dest="run_local_code",
            help="Run code locally on the machine where autoval_runner.par is installed",
        )
        self.parser.add_argument(
            "-f",
            "--func",
            type=str,
            default=None,
            dest="function_name",
            help="Name of the function to execute",
        )
        self.parser.add_argument(
            "-p",
            "--func_args",
            dest="func_args",
            default=None,
            nargs="+",
            help="Arguments to pass to the function",
        )
        self.parser.add_argument(
            "--save_console_log",
            dest="save_console_log",
            action="store_true",
            help="Save AutoVal logger output in logfile",
        )

        return self.parser

    def _initialize_config(self):
        config = None
        if self.args.config:
            try:
                config = self._read_json_file(self.args.config)
            except ValueError as e:
                raise CLIException(
                    f"Failed to parse config JSON file {self.args.config}:\n{str(e)}"
                )
        return config

    def _initialize_test_control(self):
        test_control = {}
        if self.args.test_control:
            test_control = self._read_file(file_path=self.args.test_control)

        if self.args.cli_args:
            test_control.update(self.parse_cli_args(self.args.cli_args))

        return test_control

    def _read_file(self, file_path: str) -> str:
        _file = {}
        try:
            # Find control file inside test_module folder
            _path = "/".join(self.test_module.split(".")[2:-1])
            _path += "/" + file_path
            _file = GenericUtils.read_resource_cfg(file_path=_path)
        except Exception:
            try:
                # If the file is provided outside of the par file just use the
                # path as given
                _file = self._read_json_file(file_path)
            except (ValueError, FileNotFoundError) as e:
                raise CLIException(f"Failed to parse JSON file: {file_path}\n {str(e)}")

        return _file

    def _read_json_file(self, control_path: str):
        from autoval.lib.utils.file_actions import FileActions

        return FileActions.read_data(control_path, json_file=True)

    def _write_json_file(self, control_path: str, data: str) -> None:
        from autoval.lib.utils.file_actions import FileActions

        return FileActions.write_data(control_path, data)

    def parse_cli_args(self, cli_args):
        # User can overwrite test_control settings through --args parameter.
        # Data can be either provided in json structure matching the
        # test_control file or in comma-separated key-value pairs separated
        # by ":"
        # Json Sample:
        # --args '{"runtime": 3600, "cycle_type": "reboot"}'
        # comma-separated sample:
        # --args "runtime: 3600, cycle_type: reboot"
        try:
            try:
                cli_args = json.loads(cli_args)
            except Exception:
                arg_list = cli_args.split(",")
                cli_args = {}
                for arg in arg_list:
                    kv = arg.split(":")
                    v = kv[1].strip()
                    try:
                        # Try to auto-convert type of value
                        v = literal_eval(v)
                    except Exception:
                        pass
                    cli_args[kv[0].strip()] = v

            return cli_args
        except Exception as e:
            raise CLIException("Invalid --args specified: {}".format(str(e)))

    def _extract_test_control(self) -> None:
        tmp_dir = tempfile.mkdtemp()
        test_control_path = os.path.join(tmp_dir, "test_control.json")
        self._write_json_file(test_control_path, self.test_control)
        print("extracted test_control to: {}".format(test_control_path))


def main() -> None:
    cmd_parse = AutoValCLI()
    pprint(cmd_parse.config)


if __name__ == "__main__":
    main()
