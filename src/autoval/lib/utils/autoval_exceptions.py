#!/usr/bin/env python3
import enum
from typing import Optional, Union

from autoval.lib.utils.autoval_errors import ErrorType

# Maximum lines/characters to be displayed on logs
MAX_STEP_LINES = 10
MAX_STEP_CHARS = 250


class FolderTransferErrorCodes(enum.Enum):
    NO_ERROR = -1
    UNKNOWN = 0
    OTHER = 1
    REMOTE_TAR_ERROR = 2
    REMOTE_UNTAR_ERROR = 3
    LOCAL_TAR_ERROR = 4
    LOCAL_UNTAR_ERROR = 5
    REMOTE_REMOVAL_ERROR = 6
    LOCAL_REMOVAL_ERROR = 7
    REMOTE_FOLDER_DOES_NOT_EXIST = 8
    LOCAL_FOLDER_DOES_NOT_EXIST = 9
    REMOTE_FOLDER_CREATION_ERROR = 10
    LOCAL_FOLDER_CREATION_ERROR = 11
    DATA_TRANSFER_ERROR = 12


class TestStepSeverity(enum.Enum):

    INFO = "INFO"
    ERROR = "ERROR"
    FATAL = "FATAL"
    WARNING = "WARNING"
    UNKNOWN = "UNKNOWN"


class AutoValException(Exception):
    """
    Base exception type with custom implementation for AutoVal
    """

    # pyre-fixme[3]: Return type must be annotated.
    def __init__(
        self,
        message: Optional[str] = None,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        exception: Optional[Exception] = None,
    ):
        """AutoValException extends Python's Exception class and adds the notion of component and error type.
           Many a times, we want to wrap an underlying exception and propogate the same error type and component information.
           For that, it accepts an exception argument

        Args:
            message: Description or error message
            component: component where this error occurred
            error_type: Error type for this exception
            exception: Exception upon which this AutoValException is derived from
        """
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = None
        # pyre-fixme[4]: Attribute must be annotated.
        self.component = None
        # pyre-fixme[4]: Attribute must be annotated.
        self.error_type = None
        # pyre-fixme[4]: Attribute must be annotated.
        self.identifier = None
        self.exception = exception
        if exception:
            self.message = AutoValException.truncate(str(exception))
            self.component = getattr(exception, "component", None)
            self.error_type = getattr(exception, "error_type", None)
            self.identifier = getattr(exception, "identifier", None)
        if message is not None:
            self.message = AutoValException.truncate(message)
        if component is not None:
            self.component = component
        if error_type is not None:
            self.error_type = error_type
        if identifier is not None:
            self.identifier = identifier

    def __str__(self) -> str:
        return self.message

    @classmethod
    def truncate(cls, data: str, length: int = 65534) -> str:
        """
        Truncates string into shorter ones for prettier printing
        default length is aligned to the size of sql text
        """
        orig_len = len(str(data))
        if orig_len >= (length):
            truncated = orig_len - length
            truncate_pattern = f" ... ({truncated} characters truncated) ... "
            substr_length = int((length - len(truncate_pattern)) / 2)
            return data[:substr_length] + truncate_pattern + data[-substr_length:]
        return data

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def autoval_utils(cls):
        """
        imports and returns AutovalUtils class
        """
        from autoval.lib.utils.autoval_utils import AutovalUtils

        return AutovalUtils


class TestError(AutoValException):
    def __init__(
        self,
        message: str = "Test Error",
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        exception: Optional[Exception] = None,
    ) -> None:
        super().__init__(
            message=message,
            component=component,
            error_type=error_type,
            identifier=identifier,
            exception=exception,
        )

    def __str__(self) -> str:
        return f"[AUTOVAL TEST ERROR] {self.message}"


class HostException(AutoValException):
    """Host object exceptions"""

    def __init__(
        self,
        message: str = "Host Error",
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=ErrorType.NOT_ACCESSIBLE_ERR,
    ) -> None:
        super().__init__(message=message, component=component, error_type=error_type)
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = AutoValException.truncate(message)

    def __str__(self) -> str:
        return "[AUTOVAL HOST ERROR] %s" % self.message


class ConnectionError(AutoValException):
    def __init__(
        self,
        identifier: str = "",
        message: str = "Connection Error",
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=ErrorType.NOT_ACCESSIBLE_ERR,
    ) -> None:
        message = f"{identifier}: {message}"
        super().__init__(message=message, component=component, error_type=error_type)
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = AutoValException.truncate(message)

    def __str__(self) -> str:
        return "[AUTOVAL HOST ERROR] %s" % self.message


class TestInputError(AutoValException):
    """This error is to represent Test input errors such as errors in test control or test args"""

    def __init__(
        self,
        message: str = "Test Input Error",
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=ErrorType.INPUT_ERR,
    ) -> None:
        super().__init__(message=message, component=component, error_type=error_type)
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = AutoValException.truncate(message)

    def __str__(self) -> str:
        return f"[AUTOVAL TEST INPUT ERROR] {self.message}"


class CmdError(AutoValException):
    def __init__(
        self,
        command: str,
        # pyre-fixme[2]: Parameter must be annotated.
        result_obj,
        # pyre-fixme[2]: Parameter must be annotated.
        additional_text=None,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=ErrorType.CMD_ERR,
    ) -> None:
        super().__init__(
            message="",
            component=component,
            error_type=error_type,
        )
        self.command = command
        # pyre-fixme[4]: Attribute must be annotated.
        self.result_obj = result_obj
        # pyre-fixme[4]: Attribute must be annotated.
        self.additional_text = AutoValException.truncate(additional_text)

    def __str__(self) -> str:
        msg = "Command <%s> failed, rc=%d" % (self.command, self.result_obj.return_code)
        if self.additional_text:
            msg += ", " + self.additional_text
        msg += "\n%s" % (self.result_obj.stdout + self.result_obj.stderr)
        end_msg = ""
        if len(msg.split("\n")) > MAX_STEP_LINES or (
            len(msg.split("\n")) == 1 and len(msg) > MAX_STEP_CHARS
        ):
            end_msg = "\nPlease refer cmdlog.log for complete output."
        msg = AutoValException.autoval_utils().get_concise_step_log(msg)
        if end_msg:
            msg = msg + end_msg
        return "[AUTOVAL CMD ERROR] %s" % msg


class ToolError(AutoValException):
    def __init__(
        self,
        message: str = "Tool Error",
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        error_type: Union[ErrorType, None] = None,
        exception: Optional[Exception] = None,
    ) -> None:
        super().__init__(
            message=message,
            component=component,
            error_type=ErrorType.TOOL_ERR,
            exception=exception,
        )

    def __str__(self) -> str:
        return f"[AUTOVAL TOOL ERROR] {self.message}"


class TimeoutError(AutoValException):
    def __init__(
        self,
        message: str = "Timeout Error",
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=ErrorType.CMD_TIMEOUT_ERR,
    ) -> None:
        super().__init__(message=message, component=component, error_type=error_type)
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = AutoValException.truncate(message)

    def __str__(self) -> str:
        return "[AUTOVAL TIMEOUT ERROR] %s" % self.message


class SystemInfoException(AutoValException):
    def __init__(
        self,
        message: str = "System Info Error",
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
    ) -> None:
        super().__init__(message=message, component=component, error_type=error_type)
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = AutoValException.truncate(message)

    def __str__(self) -> str:
        return "[HAVOC SYSTEM INFO ERROR] %s" % self.message


class AutovalFileError(AutoValException):
    def __init__(
        self,
        message: str = "Autoval File Error",
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=ErrorType.STORAGE_SERVICE_ERR,
    ) -> None:
        super().__init__(message=message, component=component, error_type=error_type)
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = AutoValException.truncate(message)

    def __str__(self) -> str:
        return "[Autoval FILE ERROR] %s" % self.message


class AutovalFileNotFound(AutoValException):
    def __init__(self, message: str = "Autoval File Not Found Error") -> None:
        super().__init__()
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = AutoValException.truncate(message)
        # pyre-fixme[4]: Attribute must be annotated.
        self.error_type = ErrorType.TEST_SCRIPT_ERR

    def __str__(self) -> str:
        return "[FILE NOT FOUND ERROR] %s" % self.message


class CLIException(Exception):
    """Package object exceptions"""

    def __init__(self, message: str = "CLI Error") -> None:
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = AutoValException.truncate(message)

    def __str__(self) -> str:
        return "[AUTOVAL CLI ERROR] %s" % self.message


class FolderTransferError(Exception):
    def __init__(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        msg,
        # pyre-fixme[2]: Parameter must be annotated.
        *args,
        code: FolderTransferErrorCodes = FolderTransferErrorCodes.UNKNOWN,
    ) -> None:
        self.code = code
        super().__init__(msg, *args)


class NotSupported(Exception):
    def __init__(self, message: str = "Action Not Supported") -> None:
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = AutoValException.truncate(message)

    def __str__(self) -> str:
        return "[NOT SUPPORTED] %s" % self.message


class PasswordNotFound(Exception):
    pass


class TestStepError(Exception):
    def __init__(self, message: str = "Test Step Error") -> None:
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = AutoValException.truncate(message)

    def __str__(self) -> str:
        return "[AUTOVAL TEST STEP ERROR] %s" % self.message


class InvalidTestInputError(AutoValException):
    def __init__(self, message: str = "Invalid Test Input Error") -> None:
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = AutoValException.truncate(message)
        # pyre-fixme[4]: Attribute must be annotated.
        self.error_type = ErrorType.INPUT_ERR

    def __str__(self) -> str:
        return "[AUTOVAL INVALID TEST INPUT ERROR] %s" % self.message


class AMDSMIError(AutoValException):
    """This error is to represent AMD-SMI errors observed while executing AMD-SMI Tool Commands"""

    def __init__(
        self,
        message: str = "AMD-SMI Error",
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
    ) -> None:
        super().__init__(message=message, component=component, error_type=error_type)
        # pyre-fixme[4]: Attribute must be annotated.
        self.message = AutoValException.truncate(message)

    def __str__(self) -> str:
        return f"[AUTOVAL AMDSMI ERROR] {self.message}"
