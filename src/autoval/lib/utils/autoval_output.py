import os
import sys
import threading
import typing as ty


# pyre-fixme[5]: Global expression must be annotated.
_version = (
    (float)(sys.version_info[0])
    + (0.1 * (float)(sys.version_info[1]))
    + (0.01 * (float)(sys.version_info[2]))
)

try:
    if _version >= 3.7:
        import ocptv.output as tv
        from ocptv.output import (
            DiagnosisType,
            LogSeverity,
            TestStatus,
            Validator,
            ValidatorType,
            Writer,
        )

        from autoval.lib.utils.autoval_errors import ErrorType

        # pyre-fixme[5]: Global expression must be annotated.
        OPERATION_OCP_VALIDATOR_MAP = {
            "isEqual": ValidatorType.EQUAL,
            "isNotEqual": ValidatorType.NOT_EQUAL,
            "lt": ValidatorType.LESS_THAN,
            "lte": ValidatorType.LESS_THAN_OR_EQUAL,
            "gt": ValidatorType.GREATER_THAN,
            "gte": ValidatorType.GREATER_THAN_OR_EQUAL,
            "RegexMatch": ValidatorType.REGEX_MATCH,
            "RegexNotMatch": ValidatorType.REGEX_NO_MATCH,
            "isIn": ValidatorType.IN_SET,
            "isNotException": ValidatorType.EQUAL,
        }

        # pyre-fixme[5]: Global expression must be annotated.
        LOG_LEVEL_MAP = {
            "INFO": LogSeverity.INFO,
            "ERROR": LogSeverity.ERROR,
            "WARN": LogSeverity.WARNING,
            "DEBUG": LogSeverity.DEBUG,
        }
except Exception:
    pass

OUTPUT_FILE = "ocp_output.jsonl"


class Verdict:
    """Class to hold verdicts for test steps"""

    PASS = "test-step-passed"
    FAIL = "test-step-failed"


class AutovalOutput:
    """Class to handle output for Autoval tests"""

    # pyre-fixme[4]: Attribute must be annotated.
    run = None
    # pyre-fixme[4]: Attribute must be annotated.
    ocp_diag_enabled = None

    @staticmethod
    def is_ocp_diag_enabled() -> bool:
        """Check if OCP diag output is enabled.

        Returns:
            bool: True if OCP diag output is enabled, False otherwise.
        """
        if AutovalOutput.ocp_diag_enabled is None:
            from autoval.lib.test_args import TEST_CONTROL
            from autoval.lib.utils.site_utils import SiteUtils

            site_setting = False
            site_setting = SiteUtils.get_site_setting(
                "enable_ocp_diag_output", raise_error=False
            )
            is_enabled = TEST_CONTROL.get("enable_ocp_diag_output", site_setting)
            AutovalOutput.ocp_diag_enabled = is_enabled
        return AutovalOutput.ocp_diag_enabled

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def start_test_run(test):
        """Start a new test run.

        Args:
            test: The test object.
        """
        if not AutovalOutput.is_ocp_diag_enabled():
            return
        dut = tv.Dut(id=test.hostname, name=test.hostname)
        tv.config(writer=AutovalOutput._get_test_output_file_writer())
        AutovalOutput.run = tv.TestRun(
            name=test.test_name, version="1.0", parameters=test.test_control
        )

        AutovalOutput.run.start(dut=dut)

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def end_test_run(test):
        """End the current test run.

        Args:
            test: The test object.
        """
        if not AutovalOutput.is_ocp_diag_enabled():
            return
        result = (
            tv.TestResult.PASS
            if test.test_status.value == "TEST PASSED"
            else tv.TestResult.FAIL
        )
        AutovalOutput.run.end(status=tv.TestStatus.COMPLETE, result=result)
        from autoval.lib.utils.site_utils import SiteUtils

        source_path = AutovalOutput.get_test_output_file_path()
        target_path = os.path.join(SiteUtils.get_resultsdir(), OUTPUT_FILE)
        from autoval.lib.utils.file_actions import FileActions

        FileActions.copy_from_local(None, source_path, target_path)

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def add_measurement(name, value):
        """Add a measurement to the current test step.

        Args:
            name: The name of the measurement.
            value: The value of the measurement.
        """
        if not AutovalOutput.is_ocp_diag_enabled():
            return
        global run
        run_step = AutovalOutput.run.add_step(name)
        run_step.start()
        run_step.add_measurement(name=name, value=value)
        run_step.end(status=TestStatus.COMPLETE)

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def add_test_step(**kwargs):
        """Add a test step to the current test run.

        Args:
            name: The name of the test step. Defaults to "test-step".
            operation: The operation to perform on the measurement. Defaults to None.
            measurement_name: The name of the measurement. Defaults to "measurement".
            did_pass: Whether the test step passed or failed. Defaults to False.
            error_type: The type of error that occurred. Defaults to None.
            actual: The actual value of the measurement. Defaults to None.
            expected: The expected value of the measurement. Defaults to None.
            msg: A message to include with the diagnosis. Defaults to None.
        """
        if not AutovalOutput.is_ocp_diag_enabled():
            return
        step_name = kwargs.get("name", "test-step")
        if step_name is None:
            step_name = "test-step"
        operation = kwargs.get("operation")
        measurement = kwargs.get("measurement_name", "measurement")
        if measurement is None:
            measurement = "measurement"
        did_pass = kwargs.get("did_pass", False)
        error_type = kwargs.get("error_type")
        actual = kwargs.get("actual")
        expected = kwargs.get("expected")
        msg = kwargs.get("msg")
        run_step = AutovalOutput.run.add_step(step_name)
        run_step.start()
        validator_type = OPERATION_OCP_VALIDATOR_MAP.get(operation, ValidatorType.EQUAL)
        expected_val = "" if expected is None else str(expected)
        actual_val = "" if actual is None else str(actual)
        validator = Validator(
            type=validator_type, value=expected_val, name=f"{operation}-validator"
        )
        run_step.add_measurement(
            name=measurement, value=actual_val, validators=[validator]
        )

        diagnosis_type = DiagnosisType.PASS if did_pass else DiagnosisType.FAIL
        verdict = Verdict.PASS if did_pass else Verdict.FAIL
        verdict = (
            error_type.value
            if error_type and error_type != ErrorType.UNKNOWN
            else verdict
        )
        run_step.add_diagnosis(
            diagnosis_type, verdict=verdict, message=msg, source_location={}
        )
        run_step.end(status=TestStatus.COMPLETE)

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def log(severity, msg):
        """Log a message with the specified severity.

        Args:
            severity: The severity of the message.
            msg: The message to log.
        """
        if not AutovalOutput.is_ocp_diag_enabled():
            return
        AutovalOutput._add_run_log(LOG_LEVEL_MAP[severity], msg)

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def _add_run_log(severity, msg):
        """Add a log message to the current test run.

        Args:
            severity: The severity of the message.
            msg: The message to log.
        """
        try:
            AutovalOutput.run.add_log(
                severity=severity, message=msg, source_location={}
            )
        except Exception:
            pass

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_test_output_file_path():
        """Get the path to the output file for the current test run.

        Returns:
            The path to the output file.
        """
        from autoval.lib.utils.site_utils import SiteUtils

        path = SiteUtils.get_control_server_tmpdir()
        return os.path.join(path, OUTPUT_FILE)

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    def _get_test_output_file_writer():
        """Get a writer object for writing to the output file.

        Returns:
            A writer object for writing to the output file.
        """

        class FileSyncWriter(Writer):
            def __init__(self, file: ty.TextIO):
                self.__file = file
                self.__lock = threading.Lock()

            def write(self, buffer: str):
                with self.__lock:
                    self.__file.write(f"{buffer}\n")
                    self.__file.flush()

        return FileSyncWriter(open(AutovalOutput.get_test_output_file_path(), "a"))
