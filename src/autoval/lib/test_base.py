#!/usr/bin/env python3
"""Library for TestBase and TestStatus classes"""
import abc

import logging

import os
import re
import sys
import time
from enum import Enum
from typing import List

import six

import autoval.lib.utils.decorators as av_deco
from autoval.lib.host.host import Host
from autoval.lib.test_args import TEST_CONFIG, TEST_CONTROL, TEST_HOSTS, TestArgs
from autoval.lib.test_utils.bg_runner import BgMonitor
from autoval.lib.utils.autoval_errors import ErrorType, TEST_SCRIPT_ERRORS
from autoval.lib.utils.autoval_exceptions import AutoValException, TestStepError
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.autoval_output import AutovalOutput as autoval_output

from autoval.lib.utils.autoval_utils import AutovalUtils
from autoval.lib.utils.result_handler import ResultHandler
from autoval.lib.utils.site_utils import SiteUtils


# pyre-fixme[3]: Return type must be annotated.
# pyre-fixme[2]: Parameter must be annotated.
def _exc_handler(func):
    """
    Decorate an object method.
    If method call raises, calls "_handle_exception" on same object with the caught exception.
    The "_handle_exception" method is assumed to exist.
    """

    # pyre-fixme[53]: Captured variable `func` is not annotated.
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def wrapper(self, *args, **kwargs):
        try:
            func(self, *args, **kwargs)
        except Exception as e:
            self._handle_exception(e)

    return wrapper


class TestStatus(Enum):
    """Class for all available test statuses"""

    PASSED = "TEST PASSED"
    RUNNING = "TEST RUNNING"
    FAILED = "TEST FAILED"
    WARNING = "TEST WARNING"  # TODO: Need to check other changes required for this
    PASSED_WITH_WARNING = "TEST PASSED WITH WARNING"

    def __str__(self) -> str:
        return self.value


@six.add_metaclass(abc.ABCMeta)
class TestBase:
    """A TestBase class whose instances are single tests.

    From it's inception to death, it goes through lifecycle events in the following order:
    setup -> execute -> teardown -> process_results.

    Test authors should subclass TestBase and provide an implementation of
    'execute' method for their own tests.
    Construction and deconstruction of the test's environment can be
    implemented by overriding the 'setup' and 'teardown' methods respectively.

    If it is necessary to override the __init__ method, the TestBase's
    __init__ method must always be called. It is important that subclasses
    should not change the signature of their __init__ method, since instances
    of the classes are instantiated automatically by parts of the TestBase
    runner framework in order to be run.

    TestBase uses customizable modules and hooks during it's lifecycle
    to provide additional features.

    To get started, refer to lib/tests/connecttest/new_connect_test.py
    """

    def __init_subclass__(cls) -> None:
        if hasattr(cls, "__doc__") and cls.__doc__:
            # pyre-fixme[16]: Optional type has no attribute `rstrip`.
            # pyre-fixme[4]: Attribute must be annotated.
            cls._doc = cls.__doc__.rstrip()
        else:
            cls._doc = ""
        return super(TestBase, cls).__init_subclass__()

    def __init__(
        self,
    ) -> None:
        self.autoval_log = AutovalLog()
        self.result_handler = ResultHandler()
        # pyre-fixme[4]: Attribute must be annotated.
        self.configchecker = None
        # pyre-fixme[4]: Attribute must be annotated.
        self.test_name = type(self).__name__
        # pyre-fixme[4]: Attribute must be annotated.
        self.test_start_time = time.time()
        # pyre-fixme[4]: Attribute must be annotated.
        self.test_status = TestStatus.RUNNING
        # pyre-fixme[4]: Attribute must be annotated.
        self.config = TEST_CONFIG
        # pyre-fixme[4]: Attribute must be annotated.
        self.debug = TestArgs().debug
        # pyre-fixme[4]: Attribute must be annotated.
        self.test_control = TEST_CONTROL
        self.is_teardown_called = False
        # These are set in Siteutils
        # pyre-fixme[4]: Attribute must be annotated.
        self.system_log_dir = None
        # pyre-fixme[4]: Attribute must be annotated.
        self.resultsdir = None
        # pyre-fixme[4]: Attribute must be annotated.
        self.hosts = TEST_HOSTS
        # pyre-fixme[4]: Attribute must be annotated.
        self.hostname = None
        if self.hosts and len(self.hosts) > 0:
            self.hostname = self.hosts[0].get("hostname", None)

        # pyre-fixme[4]: Attribute must be annotated.
        self.connect_to_host = self.test_control.get("connect_to_host", True)
        # pyre-fixme[4]: Attribute must be annotated.
        self.bg_monitor_args = self.test_control.get("bg_monitor", None)

        # Initializes the log directory, can't run any commands before this
        SiteUtils.init_logdirs_on_control_server(self)
        # pyre-fixme[4]: Attribute must be annotated.
        self.host_objs = []
        # pyre-fixme[4]: Attribute must be annotated.
        self.host = None
        # pyre-fixme[4]: Attribute must be annotated.
        self.localhost = None

    def lifecycle(self) -> None:
        """
        Implements the lifecycle of the TestBase.
        setup -> execute -> teardown -> process_results

        Tests should never use or override this method.
        It is used by Autoval test runner to run the test.
        """
        try:
            self._start_test()
            try:
                self._setup_execute_teardown()
            finally:
                self._set_final_test_status()
                if self.test_status == TestStatus.FAILED:
                    with av_deco.PytestLive(step="on_fail", class_instance=self):
                        self.on_fail()
        finally:
            self._end_test()

    def get_return_code(self) -> int:
        """
        Get a process exit code based on test outcome. If a test assertion failed (where
        `self.test_status` is not a PASSED variant), return constant 2.
        Otherwise, exit code is 0, meaning test passed and process exited successfully.
        """
        ret_code = 0
        if self.test_status not in [TestStatus.PASSED, TestStatus.PASSED_WITH_WARNING]:
            ret_code = 2

        return ret_code

    @_exc_handler
    def _start_test(self) -> None:
        """
        This is the beginning of an AutoVal test
        It prints the test mode and test start message
        """
        # Set a reference to this test object in ResultHandler
        self.result_handler.test = self
        # Set the results dir base path in result handler
        self.result_handler.results_dir = self.resultsdir
        # self.result_handler.start()
        autoval_output.start_test_run(self)
        """  _msg = "Test Mode detected for this run - "
        _msg += f"{self.test_mode_obj.__class__.__name__ if self.test_mode_obj is not None else ''}" """
        # self.log_info(_msg)
        self._initialize_host(not self.connect_to_host)
        if self.connect_to_host:
            hosts = []
            # self.host.add_test_start_msg(test_name=self.test_name)
            for host in self.hosts:
                # take only left part of hostname if match else full hostname
                match = re.search(r"(^\D+\w+.*)(\.\w+\.\w+)", host["hostname"])
                hosts.append(match.group(1) if match else host["hostname"])
            SiteUtils.init_logdirs_on_test_host(self)
        else:
            hosts = [
                "Unknown hostname",
            ]
        self.initialize_config_check()
        self.log_info(
            "Starting test {} on {}".format(self.test_name, ", ".join(h for h in hosts))
        )

    def _initialize_host(self, skip_health_check: bool = False) -> None:
        self.host_objs = Host.get_hosts_objs()
        if self.connect_to_host:
            for host in self.host_objs:
                host.ping()
        self.host = self.host_objs[0]
        self.localhost = self.host.localhost

    def _setup_execute_teardown(self) -> None:
        try:
            self._setup_execute()
        finally:
            with av_deco.PytestLive(step="teardown", class_instance=self):
                self._teardown()

    def _process_test_result(self) -> None:
        """
        Handles processing of the test results
        1. _save_results() : This saves the test results in the results dir
        2. _save_cmd_metrics() : Saves different metrics about the test
        """
        try:
            self._save_results()
            self._save_cmd_metrics()
        except Exception as exception:
            self._handle_exception(exception)

    # pyre-fixme[2]: Parameter must be annotated.
    def on_fail(self, **kwargs) -> None:
        """
        Last step of the test lifecycle
        This can be overridden by the test
        to perform additional processing on test failure.
        """
        # try:
        #    self._backup_sys_logs()
        # except Exception as ex:
        #    self.log_info(
        #        f"Encountered error while taking backup of system logs ({ex})"
        #    )
        for host in self.host_objs:
            try:
                host.on_fail(**kwargs)
            except Exception as exc:
                self.log_error(
                    f"Encountered error during failure processing on host {host.hostname} ({exc})"
                )

    # pyre-fixme[2]: Parameter must be annotated.
    def register_configchecker(self, custom_configchecker) -> None:
        """
        Register a custom config checker implementation

        This needs to be invoked before calling super().setup()
        from child test class. We must take care to pass only the
        class ref and NOT the object of the custom configchecker
        implementation. This is to avoid circular dependency with
        TestBase.
        """
        self.configchecker = custom_configchecker

    # pyre-fixme[2]: Parameter must be annotated.
    def register_result_handler(self, custom_result_handler) -> None:
        """
        Register a custom result handler implementation

        This needs to be invoked before calling super().setup()
        from child test class. We need to pass the custom result
        handler implementaiton object.
        """
        self.result_handler = custom_result_handler

    def _end_test(self) -> None:
        """
        Cleanup test run log directories and call resulthandler to
        print the test summary
        """
        if self.host is not None and self.connect_to_host:
            try:
                # self.host.add_test_end_msg(self.test_name)
                pass
            except Exception as ex:
                AutovalLog.log_error(
                    f"Error occurred during adding test end marker in SEL. Reason : {ex}"
                )
                self._handle_exception(ex, False)
        AutovalLog.log_debug("Cleaning up log directories")
        autoval_output.end_test_run(self)
        try:
            SiteUtils.cleanup_log_directories(self.host_objs, self.connect_to_host)
        except Exception as ex:
            AutovalLog.log_error(
                f"Error occurred during cleanup of log directories. Reason : {ex}"
            )
            self._handle_exception(ex, False)

        self._process_test_result()
        self.result_handler.print_test_summary()

    def _host_pre_test_operations(self, host_objs: List[Host]) -> None:
        """Arbitrary pre-test actions taken on each host."""
        pass

    # pyre-fixme[3]: Return type must be annotated.
    def setup(self, config_check: bool = True):
        """
        Constructs a test's environment.
        This method is called once before test is executed.

        It does the following:
        1) Checks if all hosts are reachable
        2) Initializes log directories on hosts aka DUTs
        3) Collects system configurations, if enabled
        3) Executes pre_test_operations based on TestMode
        4) Start background monitors if available

        Subclasses of TestBase can override it to setup test specific environment.
        While overriding setup, subclasses must always call TestBase's setup
        and it must be the first statement.

        Example:
            def setup():
                super().setup()
                // set-up test specific environment
        """
        # This is to provide backward compatibility to old tests
        # which pass configuration related flags as args
        # The support for this will be removed in a later version
        # self.configchecker.config_comparison = config_check
        # Perform Test Mode specific Pre test Operations.
        # self.test_mode_obj.pre_test_operations(self.host_objs)
        # Adding this after the MC and other checks
        self._host_pre_test_operations(self.host_objs)
        # Pre test config collection
        """ self.configchecker.pretest_config(
            start_time=self.test_start_time,
            system_logdir=self.system_log_dir,
            run_config_check_in_parallel=self.test_control.get(
                "run_config_check_in_parallel", True
            ),
        ) """
        self._start_bg_operations()
        if self.test_control.get("device_init"):
            self.device_init()

    # pyre-fixme[3]: Return type must be annotated.
    def device_init(self):
        """prior-test device specific initialization(s) for emulator hosts"""
        for host in self.host_objs:
            try:
                if hasattr(host, "devices") and host.devices.num_devices > 0:
                    host.devices.device_init()
            except Exception as err:
                AutovalLog.log_debug(str(err))

    def get_test_params(self) -> str:
        """
        Return the list of params for a test (in a str), but this default
        return an empty string to be used by tests that don't supply
        a test_param list or have no paramaters
        This is used in constructing the test_sumamry.
        """
        return ""

    @_exc_handler
    def _setup_execute(self) -> None:
        self._setup()
        with av_deco.PytestLive(step="execute", class_instance=self):
            self.execute()

    def _setup(self) -> None:
        with av_deco.PytestLive(step="setup", class_instance=self):
            self.setup()

    @_exc_handler
    def _teardown(self) -> None:
        self.cleanup()
        if not self.is_teardown_called:
            self.teardown()

    # pyre-fixme[2]: Parameter must be annotated.
    def _handle_exception(self, exception, re_raise=True) -> None:
        """
        This method handles all the user defined / python exceptions
        throughout the test lifecyle
        """
        self.test_status = TestStatus.FAILED
        if not isinstance(exception, TestStepError):
            _component = None
            _error_type = None
            _identifier = None

            if exception.__class__.__name__ in TEST_SCRIPT_ERRORS:
                _error_type = ErrorType.TEST_SCRIPT_ERR

            elif isinstance(exception, AutoValException):
                _component = exception.component
                _error_type = exception.error_type
                _identifier = exception.identifier

            self.validate_condition(
                False,
                str(exception),
                identifier=_identifier,
                raise_on_fail=False,
                component=_component,
                error_type=_error_type,
            )
        if re_raise:
            raise

    @abc.abstractmethod
    # pyre-fixme[3]: Return type must be annotated.
    def execute(self):
        """
        This is an abstract method which has to be overridden by child test classes
        to provide meaningful functionality to a test. The main logic of the test
        is expected to be implemented in the execute method.
        """
        return

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def cleanup(self, cfg_filter=None, config_check: bool = True, config_data=None):
        """
        This is to maintain backwards compatibility with existing tests.
        We intercept args passed to cleanup and set configchecker using API
        """
        """ self.configchecker.cfg_filter = cfg_filter
        self.configchecker.config_comparison = config_check
        self.configchecker.config_data = config_data """
        self.is_teardown_called = True
        self.teardown()

    # pyre-fixme[3]: Return type must be annotated.
    def teardown(self):
        """
        This method is called at the end of the test.
        This does the following:
        1) Stops background operations (if any)
        2) Triggers post test configuration collection / comparison
        3) Perform post test operations depending on test mode

        Example:
            def teardown(self):
                // Teardown logic for the test
                super().teardown()
        """
        try:
            self._stop_bg_operations()
        finally:
            AutovalLog.log_debug("Post test operations completed")

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_test_results_file_path(self, file_name):
        """
        Returns the path for the test result files
        Args:
            file_name (string): The test result filename

        Returns:
            string: The complete file path
        """
        file_path = os.path.join(self.resultsdir, "%s" % file_name)
        return file_path

    def _save_results(self) -> None:
        self.result_handler.save_test_results()

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def __getattr__(self, name):
        # Allows to directly call methods on the test object that are defined
        # in AutovalUtils module, AutovalLog module
        if name in [
            "log_cmdlog",
            "log_as_cmd",
            "log_info",
            "log_debug",
            "log_warning",
            "log_error",
        ]:
            return getattr(self.autoval_log, name)
        return getattr(AutovalUtils, name)

    def _save_cmd_metrics(self) -> None:
        file_path = self.get_test_results_file_path("cmd_metrics.json")
        self.result_handler.save_cmd_metrics(file_path)

    def _start_bg_operations(self) -> None:
        if self.bg_monitor_args is not None:
            try:
                for host in self.host_objs:
                    BgMonitor.start_monitors(host, self.bg_monitor_args)
            except Exception as _e:
                self.log_info("Failure in Start BG operations %s" % str(_e))

    def _stop_bg_operations(self) -> None:
        try:
            BgMonitor.stop_monitors()
        except Exception as _e:
            self.log_info("Failure in BG operations %s" % str(_e))
            raise

    def _backup_sys_logs(self) -> None:
        if not hasattr(self, "dut_tmpdir") or self.dut_tmpdir is None:
            self.log_info("DUT tmpdir not defined, skipping backup")
            return
        SiteUtils.backup_dut_tmpdir(self.host_objs)

    def initialize_config_check(self) -> None:
        """
        Initialize configuration collection / verification for the test
        """
        pass

    # pyre-fixme[3]: Return type must be annotated.
    def _set_final_test_status(self):
        """
        This computes and the final test status at the end of the test

        The default status will be PASSED if status is already not marked FAILED
        If we get some warning steps then the test is marked 'Passed with Warning'
        If we get any failed steps then the test is marked as 'Failed'

        """
        failed = AutovalUtils.get_failed_test_steps()

        warning = AutovalUtils.get_warning_steps()
        if self.test_status != TestStatus.FAILED:
            self.test_status = TestStatus.PASSED
            if warning:
                self.test_status = TestStatus.PASSED_WITH_WARNING
            if failed:
                self.test_status = TestStatus.FAILED

    # pyre-fixme[2]: Parameter must be annotated.
    def add_measurement(self, name, value) -> None:
        autoval_output.add_measurement(name=name, value=value)
