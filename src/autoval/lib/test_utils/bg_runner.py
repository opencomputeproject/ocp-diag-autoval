#!/usr/bin/env python3
"""
This module allows to run test utils (implemented as TestUtils modules) in
parallel to the current test. It supports 2 use cases:
    - BgMonitor to run background monitors for the full duration of the test.
    - BgRunner to run a test in the background and stop it when needed by the
    current test
"""
# ==============================================================================
# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
#
# Description     : This util runs test in background parallel to the current
#                   test.
# ==============================================================================
import time
from collections import defaultdict

from autoval.lib.test_utils.test_utils_runner import TestUtilsRunner
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.autoval_thread import AutovalThread
from autoval.lib.utils.autoval_utils import AutovalUtils


class BgRunner:
    """BgRunner Test.

    This util will run background test and parse result of the test at
    the end. BgRunner can be initiated to run only one TestUtilsRunner
    in back ground. To run back ground tests
    in parallel to autoval test use BgMonitor which can handles multiple
    instances of BgRunner and also restart BgMonitor after system power
    cycle.
    """

    def __init__(self, host, runner) -> None:
        """Initializes the Bg Runner Test.

         This method initializes the basic configuration for logging
        information, read and store the input details
        gathered from control file having user inputs inputs.

        parameters
        ----------
        host            : :obj: 'Host'
            Host on which Bg runner needs to be run.
        runners - Dictionary(String, String)
        e.g:
            'args': {Utilargs}
            'interval': <interval to loop>,
        """
        self.host_dict = AutovalUtils.get_host_dict(host)
        self._thread = None
        self.stop_runner = False
        self.runner_name = runner["name"]
        self.runner_args = runner.get("args", None)
        self.interval = runner.get("interval", 60)
        self.runner_obj = None

    def start_bg_runner(self) -> None:
        """Start Bg Runner.

        This method start multiple thread to run Background test
        """
        if self._thread is not None:
            raise Exception("Test already running")
        self._thread = AutovalThread.start_autoval_thread(self._start_test)

    def execute_bg_runner_run_test(self) -> None:
        """This method executes only one iteration of the start_test method of the Bg Runner.

        This method should only be used after test setup has been executed. And can not be used at the same time as start_bg_runner().
        """
        if self._thread is not None:
            raise Exception("Test already running")
        self._thread = AutovalThread.start_autoval_thread(self._run_test)

    def stop_bg_runner(self) -> None:
        """Stop Bg Runner.

        This method waits for the started thread to complete and
        It stops Bg Runner once the started thread got completed.
        """
        if self._thread is not None:
            AutovalLog.log_info("Waiting for BG Runner to Complete")
            self.stop_runner = True
            AutovalThread.wait_for_autoval_thread([self._thread])
            self._thread = None

    def _start_test(self) -> None:
        """Start test.

        This method runs the Bg runner till the Bg_runner
        stop flag is triggered and parse the output data.
        """
        self.setup_test()
        # Run till the stop_bg_runners is triggered.
        while not self.stop_runner:
            self._run_test()
            time.sleep(self.interval)
        self.runner_obj.test_cleanup()

    def setup_test(self) -> None:
        from autoval.lib.host.host import Host

        host = Host(self.host_dict)
        self.runner_obj = TestUtilsRunner(host, self.runner_name, self.runner_args)
        self.runner_obj.test_setup()

    def _run_test(self) -> None:
        """Run 1 iteration of test."""
        self.runner_obj.start_test()
        self.runner_obj.parse_results()


class BgMonitor:
    """Bg Monitor Test.

    This util initialize back ground monitor and use BgRunner to runs TestUtils
    in back ground. This class help to start, stop and restart the monitors at
    different test stages i.e back ground monitors on cycle test.
    """

    active_bg_monitors = defaultdict(list)

    @classmethod
    def start_monitors(cls, host, monitors_args) -> None:
        """Start Monitors.

        This method starts Bg Monitor by starting different instance
        of Bg Runner.
        """
        if monitors_args:
            AutovalLog.log_info("Starting all active monitors")
            for runner in monitors_args:
                _runner = BgRunner(host, runner)
                cls.active_bg_monitors[host.hostname].append(_runner)
                _runner.start_bg_runner()

    @classmethod
    def stop_monitors(cls) -> None:
        """Stop Monitors.

        This method stops active Bg Monitors by stopping the Bg Runner
        instances.
        """
        if cls.active_bg_monitors:
            AutovalLog.log_info("Stopping all active monitors")
            for host_name in cls.active_bg_monitors:
                for runner_obj in cls.active_bg_monitors[host_name]:
                    runner_obj.stop_bg_runner()
            cls.active_bg_monitors = defaultdict(list)

    @classmethod
    def restart_monitors(cls) -> None:
        """Restart Monitors.

        This method restart active Bg Monitors after system power cycle.
        """
        if cls.active_bg_monitors:
            AutovalLog.log_info("Restarting all active monitors")
            for host_name in cls.active_bg_monitors:
                for runner_obj in cls.active_bg_monitors[host_name]:
                    runner_obj.start_bg_runner()
