# pyre-unsafe
"""
    UnitTest for TestBase Class
"""

import os
import sys
import unittest
from unittest import mock
from unittest.mock import patch

import autoval.lib.utils.autoval_shared_data as av_data
from autoval.lib.host.host import Host
from autoval.lib.test_args import TEST_CONTROL
from autoval.lib.test_base import TestBase, TestStatus
from autoval.lib.test_utils.bg_runner import BgMonitor
from autoval.lib.utils.autoval_exceptions import TestStepError
from autoval.lib.utils.file_actions import FileActions
from autoval.lib.utils.result_handler import ResultHandler
from autoval.lib.utils.site_utils import SiteUtils
from autoval.unittest.mock.lib.mock_host import MockHost

MOCK_INPUT_PATH = "autoval/unittest/mock/testbed/"


def setupModule():
    sys.argv = [
        "buck-out/gen/autoval/unittest/fake.par",
        "-c",
        MOCK_INPUT_PATH + "testbed.json",
    ]


class UnittestError(Exception):
    pass


class TestTestBase(TestBase):
    """
    Mock test class used for testing TestBase
    """

    @patch("autoval.lib.utils.site_utils.SiteUtils.get_resultsdir")
    @patch("autoval.lib.utils.site_utils.SiteUtils.create_resultsdir")
    @patch("autoval.lib.test_base.TestBase.initialize_config_check")
    @patch("autoval.lib.utils.site_utils.SiteUtils.init_logdirs_on_control_server")
    def __init__(
        self,
        mock_init_logdirs_on_control_server,
        mock_initialize_config,
        mock_create_resultsdir,
        mock_get_resultsdir,
    ):
        mock_create_resultsdir.return_value = "/mnt/autoval_not_exists/"
        mock_initialize_config.return_value = None
        mock_get_resultsdir.return_value = "mock_dir"
        # mock up test args to avoid any failure in test base
        TEST_CONTROL["hosts"] = {}
        TEST_CONTROL["connect_to_host"] = False
        TEST_CONTROL["bg_monitor"] = "FioRunner"
        TEST_CONTROL["disable_config_collection"] = True
        super(TestTestBase, self).__init__()

    def execute(self):
        self.log_info("This is a TestTestBase Test")


class TestBaseUnitTest(unittest.TestCase):
    """
    This Unit test will verify the functionality
    for the methods in the TestBase class.
    """

    @patch.object(os, "makedirs")
    @patch.object(Host, "get_hosts_objs")
    def setUp(self, m_get_hosts_objs, m_makedirs):
        self.host = MockHost(cmd_map=None)
        self.host.is_emulator = False
        m_makedirs.result_value = "/tmp/autoval"

        self.test_class = TestTestBase()
        self.log = ""

    def get_logger(self, out: str):
        """method will override the Autoval.log_info"""
        self.log += out

    def assert_test_summary(
        self, pass_steps=0, warn_steps=0, fail_steps=0, failed_str="", test_status=""
    ):
        """Unit Test for test_summary"""
        expected_log = (
            "+++Test Finished:\nTest Summary: TestTestBase \n    "
            "Mock test class used for testing TestBase\nPassed Steps: {}"
            "\nWarning Steps: {}\nFailed Steps: {}{}\nTest Result : {}".format(
                pass_steps, warn_steps, fail_steps, failed_str, test_status
            )
        )
        self.assertEqual(self.log, expected_log)
        self.log = ""

    @patch.object(TestBase, "on_fail")
    @patch.object(TestBase, "_process_test_result")
    @patch.object(TestBase, "_setup_execute_teardown")
    @patch.object(TestBase, "_end_test")
    @patch.object(TestBase, "_start_test")
    def test_lifecycle_ok(
        self,
        m_start_test,
        m_end_test,
        m_setup_execute_teardown,
        m_process_test_result,
        m_on_fail,
    ):
        """
        Most test just declare a test, and then call lifecycle which runs the tests
        and then prints the results.  This tests the lifecycle function's success case.
        """
        self.test_class.lifecycle()

        m_start_test.assert_called_once()
        m_end_test.assert_called_once()
        m_setup_execute_teardown.assert_called_once()
        m_on_fail.assert_not_called()

    @patch.object(TestBase, "on_fail")
    @patch.object(TestBase, "_process_test_result")
    @patch.object(TestBase, "_setup_execute_teardown")
    @patch.object(TestBase, "_end_test")
    @patch.object(TestBase, "_start_test")
    def test_lifecycle_fails_start_test(
        self,
        m_start_test,
        m_end_test,
        m_setup_execute_teardown,
        m_process_test_result,
        m_on_fail,
    ):
        """
        Test that the lifecycle does not continue if there was an error encountered
        during the test start.
        """
        m_start_test.side_effect = UnittestError

        with self.assertRaises(UnittestError):
            self.test_class.lifecycle()

        m_setup_execute_teardown.assert_not_called()
        m_on_fail.assert_not_called()
        m_end_test.assert_called_once()

    @patch.object(TestBase, "on_fail")
    @patch.object(TestBase, "_process_test_result")
    @patch.object(TestBase, "_setup_execute_teardown")
    @patch.object(TestBase, "_end_test")
    @patch.object(TestBase, "_start_test")
    def test_lifecycle_fails_test_execution(
        self,
        m_start_test,
        m_end_test,
        m_setup_execute_teardown,
        m_process_test_result,
        m_on_fail,
    ):
        """
        Test that lifecycle execution triggers the test end and on_fail events
        when there's an error during the setup_execute_teardown procedure.
        """
        m_setup_execute_teardown.side_effect = UnittestError
        self.test_class.test_status = TestStatus.FAILED

        with self.assertRaises(UnittestError):
            self.test_class.lifecycle()

        m_on_fail.assert_called_once()
        m_end_test.assert_called_once()

    @patch.object(TestBase, "_process_test_result")
    @patch.object(ResultHandler, "print_test_summary")
    @patch.object(SiteUtils, "cleanup_log_directories")
    def test_end_test(
        self,
        m_cleanup_log_directories,
        m_print_test_summary,
        m_process_test_result,
    ):
        """Unit Test for _end_test method"""

        # scenario 1: positive flow
        self.test_class.host = self.host
        self.test_class._end_test()
        m_print_test_summary.assert_called_once()
        m_process_test_result.assert_called_once()
        m_cleanup_log_directories.assert_called_once()

    @patch.object(TestBase, "_process_test_result")
    @patch.object(ResultHandler, "print_test_summary")
    @patch.object(SiteUtils, "cleanup_log_directories")
    def test_end_test_pytest_memory(
        self,
        m_cleanup_log_directories,
        m_print_test_summary,
        m_process_test_result,
    ):
        """Unit Test for _end_test method"""

        av_data.ctx_pytest_autoval.set(True)
        av_data.ctx_pytest_autoval_results_type.set("memory")
        # scenario 1: positive flow
        self.test_class.host = self.host
        self.test_class._end_test()
        m_print_test_summary.assert_called_once()
        m_cleanup_log_directories.assert_called_once()

    @patch.object(TestBase, "_process_test_result")
    @patch.object(ResultHandler, "print_test_summary")
    @patch.object(SiteUtils, "cleanup_log_directories")
    def test_end_test_no_pytest_integration(
        self,
        m_cleanup_log_directories,
        m_print_test_summary,
        m_process_test_result,
    ):
        """Unit Test for _end_test method"""

        av_data.ctx_pytest_autoval.set(False)
        # scenario 1: positive flow
        self.test_class.host = self.host
        self.test_class._end_test()

    @patch.object(TestBase, "_save_results")
    @patch.object(TestBase, "_save_cmd_metrics")
    def test_process_test_result(self, m_save_cmd_metrics, m_save_results):
        """Unit Test for process_test_result method"""

        # scenario 1: positive flow
        self.test_class._process_test_result()
        m_save_results.assert_called_once()
        m_save_cmd_metrics.assert_called_once()

        # scenarion 2: exception in Try block
        m_save_cmd_metrics.side_effect = UnittestError
        m_save_results.reset_mock()

        with self.assertRaises(UnittestError):
            self.test_class._process_test_result()

        m_save_results.assert_called_once()

    @patch.object(TestBase, "_setup")
    def test_setup(self, m_setup):
        """Unit Test for _setup method"""

        # scenario 1: positive flow
        m_setup.return_value = None
        self.test_class._setup()
        m_setup.assert_called_once()

    @patch.object(TestBase, "_start_test")
    def test_start_test(self, m_start_test):
        """Unit Test for _start_test method"""

        # scenario 1: positive run (hostname detected)
        self.test_class.connect_to_host = True
        self.test_class._start_test()
        m_start_test.assert_called_once()

    @patch.object(TestBase, "_setup_execute")
    @patch.object(TestBase, "_teardown")
    def test_setup_execute_teardown(self, m_teardown, m_setup_execute):
        """Unit Test for _setup_execute_teardown method"""

        # scenario 1: Positive flow with  no exception
        self.test_class._setup_execute_teardown()
        m_setup_execute.assert_called_once()
        m_teardown.assert_called_once()

        # scenario 2 : Exception on  _setup_execute
        m_teardown.reset_mock()
        m_setup_execute.side_effect = UnittestError

        with self.assertRaises(UnittestError):
            self.test_class._setup_execute_teardown()

        m_teardown.assert_called_once()

    @patch.object(TestBase, "_setup")
    @patch.object(TestBase, "execute")
    def test_setup_execute(self, m_execute, m_setup):
        """Unit Test for setup_execute method"""

        # scenario 1: positive flow
        self.test_class._setup_execute()
        m_setup.assert_called_once()
        self.assertTrue(m_execute.abstractmethod())

    # Test function for teardown function(new cleanup)
    @patch.object(TestBase, "teardown")
    def test_teardown(self, m_teardown):
        """Unit Test for _teardown method"""

        # scenario 1: positive flow
        m_teardown.return_value = None
        self.test_class.teardown()
        m_teardown.assert_called_once()

        # scenario 2 : Exception on teardown
        m_teardown.side_effect = UnittestError

        with self.assertRaises(UnittestError):
            self.test_class.teardown()

    @patch.object(TestBase, "on_fail")
    def test_on_fail(self, m_on_fail):
        """Unit Test for on_fail method"""

        # scenario 1: positive flow
        self.test_class.on_fail()
        m_on_fail.assert_called_once()

        # scenario 2: exception in on_fail
        m_on_fail.side_effect = UnittestError

        with self.assertRaises(UnittestError):
            self.test_class.on_fail()

    def test_get_test_results_file_path(self):
        """Unit Test for tget_test_results_file_path method"""

        # scenario 1: positive flow
        self.test_class.resultsdir = "/m_tmp/"
        self.assertEqual(
            self.test_class.get_test_results_file_path("m_file"), "/m_tmp/m_file"
        )

    @patch.object(ResultHandler, "save_test_results")
    def test_save_results(self, m_save_test_results):
        """Unit Test for _save_results method"""

        self.test_class._save_results()
        m_save_test_results.assert_called_once()

    def test_getattr(self):
        """Unit Test for test_getattr"""

        # scenario 1 : positive flow
        names = [
            "log_cmdlog",
            "log_as_cmd",
            "log_info",
            "log_debug",
            "log_warning",
            "log_error",
        ]
        for name in names:
            self.test_class.__getattr__(name)

    @patch.object(ResultHandler, "save_cmd_metrics")
    def test_save_cmd_metrics(self, m_save_cmd_metrics):
        """Unit Test for _save_cmd_metrics method"""

        # scenario 1 : positive flow
        self.test_class.resultsdir = "/m_tmp/"
        self.test_class._save_cmd_metrics()
        m_save_cmd_metrics.assert_called_once()

    @patch.object(BgMonitor, "start_monitors")
    def test_start_bg_operations(self, m_bg_monitors):
        """Unit Test for _start_bg_operations method"""
        self.test_class.host_objs = ["host1"]
        # scenario 1: bg operation starts
        self.test_class._start_bg_operations()

        # scenario 2: bg start failed
        m_bg_monitors.reset_mock()
        self.test_class.bg_monitor_args = None
        self.test_class._start_bg_operations()
        m_bg_monitors.assert_not_called()

    @patch.object(BgMonitor, "stop_monitors")
    def test_stop_bg_operations(self, m_bg):
        """Unit Test for _stop_bg_operations method"""

        # scenario 1: positive flow
        self.test_class._stop_bg_operations()

    @patch.object(FileActions, "ls")
    @patch.object(TestBase, "_backup_sys_logs")
    def test_backup_sys_logs(self, m_backup_sys_logs, m_dir):
        """Unit Test for _backup_sys_logs method"""

        # scenario 1: positive flow
        #        self.test_class.dut_tmpdir = None
        m_dir.return_value = True
        self.test_class._backup_sys_logs()
        m_backup_sys_logs.assert_called_once()

    @patch.object(TestBase, "initialize_config_check")
    def test_initialize_config_check(self, m_initialize_config_check):
        """Unit Test for nitialize_config_check method"""

        # scenario 1 : verification done
        self.test_class.initialize_config_check()
        m_initialize_config_check.assert_called_once()

    @patch.object(SiteUtils, "init_logdirs_on_control_server")
    @patch.object(SiteUtils, "get_tmpdir")
    @patch.object(SiteUtils, "get_system_logdir")
    @patch.object(SiteUtils, "get_control_server_tmpdir")
    @patch.object(SiteUtils, "get_control_server_logdir")
    @patch.object(SiteUtils, "create_control_server_logdirs")
    def test_create_controller_log_directory(
        self,
        m_logdir,
        m_cs_logdir,
        m_cs_tmpdir,
        m_system_logdir,
        m_tmpdir,
        m_init_logdirs_on_control_server,
    ):
        """Unit Test for tcreate_controller_log_directory method"""

        m_cs_logdir.return_value = "/tmp/control_server_logdir"
        m_cs_tmpdir.return_value = "/tmp/control_server_tmpdir"
        m_system_logdir.return_value = "/tmp/system_logdir"
        m_tmpdir.return_value = "/tmp/tmpdir"
        SiteUtils.init_logdirs_on_control_server(self.test_class)
        m_init_logdirs_on_control_server.assert_called_once()

    @patch.object(SiteUtils, "get_dut_logdir")
    @patch.object(SiteUtils, "get_dut_tmpdir")
    @patch.object(SiteUtils, "init_logdirs_on_test_host")
    def test_create_dut_log_directories(
        self, m_init_logdirs_on_test_host, m_dut_tmpdir, m_dut_logdir
    ):
        """Unit Test for create_dut_log_directories method"""

        mock_host = MockHost(cmd_map=[])
        m_dut_tmpdir.return_value = {"host": "/tmp/dut_tmpdir"}
        m_dut_logdir.return_value = {"host": "/tmp/dut_logdir"}
        mock_output = "/mnt/autoval is a mountpoint"
        mock_host.update_cmd_map("mountpoint /mnt/autoval", mock_output)
        self.test_class.host = mock_host
        SiteUtils.init_logdirs_on_test_host(self.test_class)
        m_init_logdirs_on_test_host.assert_called_once()

    def test_get_return_code(self):
        """Unit Test for get_return_code method"""

        # case: Test passed
        self.test_class.test_status = TestStatus.PASSED
        self.assertEqual(self.test_class.get_return_code(), 0)

        # case: Test passed with warning
        self.test_class.test_status = TestStatus.PASSED_WITH_WARNING
        self.assertEqual(self.test_class.get_return_code(), 0)

        # case: Test failed
        self.test_class.test_status = TestStatus.FAILED
        self.assertEqual(self.test_class.get_return_code(), 2)

    @patch.object(TestBase, "on_fail")
    @patch.object(TestBase, "_process_test_result")
    @patch.object(TestBase, "_setup_execute_teardown")
    @patch.object(TestBase, "_end_test")
    @patch.object(TestBase, "_start_test")
    def test_get_return_code_when_lifecycle_ok(
        self,
        m_start_test,
        m_end_test,
        m_setup_execute_teardown,
        m_process_test_result,
        m_on_fail,
    ):
        """
        Test that expected return code is ok when lifecycle ran successfully.
        """
        self.test_class.lifecycle()
        self.assertEqual(self.test_class.get_return_code(), 0)

    @patch.object(TestBase, "on_fail")
    @patch.object(TestBase, "_process_test_result")
    @patch.object(TestTestBase, "execute")
    @patch.object(TestBase, "_teardown")
    @patch.object(TestBase, "_setup")
    @patch.object(TestBase, "_end_test")
    @patch.object(TestBase, "_start_test")
    def test_get_return_code_when_lifecycle_fails_test_execution(
        self,
        m_start_test,
        m_end_test,
        m_setup,
        m_teardown,
        m_execute,
        m_process_test_result,
        m_on_fail,
    ):
        """
        Test that expected return code signals test assertion failure
        when lifecycle failed during test execution.
        """
        m_execute.side_effect = TestStepError

        with self.assertRaises(TestStepError):
            self.test_class.lifecycle()
        self.assertEqual(self.test_class.get_return_code(), 2)

    def test_device_init(self):
        """Unit Test for device_init method"""
        # case 1 - device has asic modules
        self.test_class.host_objs = [self.host]
        self.host.devices = mock.Mock(return_value=[self.host])
        self.host.devices.num_devices = 1
        self.host.devices.device_init = mock.Mock()
        self.test_class.device_init()
        self.host.devices.device_init.assert_called_once()

        # case 2 - device has no asic modules
        self.host.devices.device_init.reset_mock()
        self.host.devices = mock.Mock(return_value=[self.host])
        self.host.devices.num_devices = 0
        self.test_class.device_init()
        self.host.devices.device_init.assert_not_called()
