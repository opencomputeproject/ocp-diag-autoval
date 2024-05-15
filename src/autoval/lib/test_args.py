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

    # pyre-fixme[4]: Attribute must be annotated.
    _instance = None

    # pyre-fixme[3]: Return type must be annotated.
    def __new__(cls, autoval_cli_parser: Optional[AutoValCLI] = None):
        """
        Creates new instance of TestArgs or return existance instance
        if already exists.
        @param autoval_cli_parser: AutoValCLI
        @value: None
        """
        if cls._instance is None:
            cls._instance = super(TestArgs, cls).__new__(cls)
            # pyre-fixme[16]: `TestArgs` has no attribute `_test_control`.
            cls._instance._test_control = {}
            # pyre-fixme[16]: `TestArgs` has no attribute `_config`.
            cls._instance._config = {}
            # pyre-fixme[4]: Attribute must be annotated.
            cls._instance._debug = False
            # pyre-fixme[16]: `TestArgs` has no attribute `_hosts`.
            cls._instance._hosts = []
        return cls._instance

    def __init__(self, autoval_cli_parser: Optional[AutoValCLI] = None) -> None:
        """
        Initializes the states of the class.
        @param autoval_cli_parser: AutoValCLI
        @value : None
        """
        # pyre-fixme[4]: Attribute must be annotated.
        self._collect_cmd_metrics = False
        if autoval_cli_parser is not None:
            self._initialized_test_data(autoval_cli_parser)

    # pyre-fixme[2]: Parameter must be annotated.
    def _initialized_test_data(self, parser) -> None:
        # pyre-fixme[16]: `TestArgs` has no attribute `_test_control`.
        self._test_control.update(parser.test_control)
        if parser.config is not None:
            # pyre-fixme[16]: `TestArgs` has no attribute `_config`.
            self._config.update(parser.config)
            # pyre-fixme[16]: `TestArgs` has no attribute `_hosts`.
            self._hosts.extend(parser.config.get("hosts"))
        self._debug = parser.debug
        self._collect_cmd_metrics = parser.test_control.get(
            "collect_cmd_metrics", False
        )

    @property
    # pyre-fixme[3]: Return type must be annotated.
    def test_control(self):
        # pyre-fixme[16]: `TestArgs` has no attribute `_test_control`.
        return self._test_control

    @property
    # pyre-fixme[3]: Return type must be annotated.
    def config(self):
        # pyre-fixme[16]: `TestArgs` has no attribute `_config`.
        return self._config

    @property
    # pyre-fixme[3]: Return type must be annotated.
    def debug(self):
        return self._debug

    @property
    # pyre-fixme[3]: Return type must be annotated.
    def hosts(self):
        # pyre-fixme[16]: `TestArgs` has no attribute `_hosts`.
        return self._hosts

    @property
    # pyre-fixme[3]: Return type must be annotated.
    def collect_cmd_metrics(self):
        return self._collect_cmd_metrics


# pyre-fixme[5]: Global expression must be annotated.
TEST_CONTROL = TestArgs().test_control
# pyre-fixme[5]: Global expression must be annotated.
TEST_CONFIG = TestArgs().config
# pyre-fixme[5]: Global expression must be annotated.
TEST_HOSTS = TestArgs().hosts
