#!/usr/bin/env python3
from typing import Optional

from autoval.cli.cli_parser import AutoValCLI


class TestArgs:
    """
    This is singleton class which shares the object instance.
    The assumption is that the class will only be initialized
    by autoval_test_runner which starts the autoval test execution
    and parse AutovalCli.
    """

    _instance = None

    def __new__(cls, autoval_cli_parser: Optional[AutoValCLI] = None):
        """
        Creates new instance of TestArgs or return existance instance
        if already exists.
        @param autoval_cli_parser: AutoValCLI
        @value: None
        """
        if cls._instance is None:
            cls._instance = super(TestArgs, cls).__new__(cls)
            cls._instance._test_control = {}
            cls._instance._config = {}
            cls._instance._debug = False
            cls._instance._hosts = []
        return cls._instance

    def __init__(self, autoval_cli_parser: Optional[AutoValCLI] = None) -> None:
        """
        Initializes the states of the class.
        @param autoval_cli_parser: AutoValCLI
        @value : None
        """
        self._collect_cmd_metrics = False
        if autoval_cli_parser is not None:
            self._initialized_test_data(autoval_cli_parser)

    def _initialized_test_data(self, parser) -> None:
        self._test_control.update(parser.test_control)
        if parser.config is not None:
            self._config.update(parser.config)
            self._hosts.extend(parser.config.get("hosts"))
        self._debug = parser.debug
        self._collect_cmd_metrics = parser.test_control.get(
            "collect_cmd_metrics", False
        )

    @property
    def test_control(self):
        return self._test_control

    @property
    def config(self):
        return self._config

    @property
    def debug(self):
        return self._debug

    @property
    def hosts(self):
        return self._hosts

    @property
    def collect_cmd_metrics(self):
        return self._collect_cmd_metrics


TEST_CONTROL = TestArgs().test_control
TEST_CONFIG = TestArgs().config
TEST_HOSTS = TestArgs().hosts
