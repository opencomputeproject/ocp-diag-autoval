#!/usr/bin/env python3
from enum import Enum
from typing import List

TEST_SCRIPT_ERRORS: List[str] = [
    "ArithmeticError",
    "AssertionError",
    "AttributeError",
    "ImportError",
    "IndentationError",
    "IndexError",
    "IndexError",
    "KeyError",
    "LookupError",
    "ModuleNotFoundError",
    "ModuleNotFoundError",
    "NameError",
    "NotImplementedError",
    "RecursionError",
    "SyntaxError",
    "TabError",
    "TypeError",
    "ValueError",
    "ZeroDivisionError",
    "UnboundLocalError",
]


class ErrorCategory(Enum):
    """
    The list contains a broader error type which can be regarded as a category
    """

    UNKNOWN = "UNKNOWN"
    AUTOMATION = "AUTOMATION"
    INFRA_TOOL = "INFRA_TOOL"
    HARDWARE = "HARDWARE"
    OS = "OS"
    CONNECTIVITY = "CONNECTIVITY"
    FIRMWARE = "FIRMWARE"
    TEST_TOOL = "TEST_TOOL"


class ErrorType(Enum):
    """
    This is a placeholder for error types.
    More types will be added to the list as per further development
    """

    __slots__ = "_value_", "error_category"

    def __init__(self, value, error_category=None):
        self._value_ = value
        self.error_category = error_category

    UNKNOWN = "UNKNOWN", ErrorCategory.UNKNOWN
    """Default type for all unspecified errors"""

    TEST_SCRIPT_ERR = "TEST_SCRIPT_ERR", ErrorCategory.AUTOMATION
    """For all programming errors/python runtime exceptions"""
    """such as “Attribute not found”, “import error”, “module not found” etc."""
    """To be used by framework only and not by tests"""

    INPUT_ERR = "INPUT_ERR", ErrorCategory.AUTOMATION
    """For all the invalid/incorrect input given to the tests Since it"""
    """represents human input error , component should be N/A"""

    SYSTEM_ERR = "SYSTEM_ERR", ErrorCategory.UNKNOWN
    """For all the unknown errors relared to components"""
    """To be used by framework only and not by tests"""

    PCIE_ERR = "PCIE_ERR", ErrorCategory.HARDWARE
    """For errors related to any pcie mismatch, primarily in config check"""

    STORAGE_SERVICE_ERR = "STORAGE_SERVICE_ERR", ErrorCategory.INFRA_TOOL
    """For errors in storage service"""

    SEL_ERR = "SEL_ERR", ErrorCategory.HARDWARE
    """For errors in sel, primarily in config check"""
    """To be used by framework only and not by tests"""

    NOT_ACCESSIBLE_ERR = "NOT_ACCESSIBLE_ERR", ErrorCategory.CONNECTIVITY
    """For connection issues if the host is not accessible either with thrift or ssh"""

    CMD_ERR = "CMD_ERR", ErrorCategory.HARDWARE
    """A broader error type for all kinds of cmd failures, usually indicating issues in firmwares"""
    """To be used by framework only and not by tests"""

    CMD_TIMEOUT_ERR = "CMD_TIMEOUT_ERR", ErrorCategory.HARDWARE
    """For command timeout errors"""
    """To be used by framework only and not by tests"""

    TOOL_ERR = "TOOL_ERR", ErrorCategory.TEST_TOOL
    """For errors due to test related tools"""

    TEST_TOPOLOGY_ERR = "TEST_TOPOLOGY_ERR", ErrorCategory.AUTOMATION
    """For all errors where topologies are not as per expectation of the test"""

    DRIVE_ERR = "DRIVE_ERR", ErrorCategory.HARDWARE
    """For errors related to drive"""

    EXPANDER_ERR = "EXPANDER_ERR", ErrorCategory.HARDWARE
    """This error is specific to bryce canyon and grand canyon platforms. Sometimes the expander is not found"""

    FIRMWARE_ERR = "FIRMWARE_ERR", ErrorCategory.FIRMWARE
    """For errors related to firmware"""

    FIRMWARE_UPGRADE_ERR = "FIRMWARE_UPGRADE_ERR", ErrorCategory.FIRMWARE
    """For errors related to upgrade in firmware"""

    NVME_ERR = "NVME_ERR", ErrorCategory.HARDWARE
    """For errors related to nvme"""

    SMART_COUNTER_ERR = "SMART_COUNTER_ERR", ErrorCategory.HARDWARE
    """For errors during SSD Smart Counter Check"""

    STORAGE_DRIVE_DEVICE_NAMES_CHANGED_ERR = (
        "STORAGE_DRIVE_DEVICE_NAMES_CHANGED_ERR",
        ErrorCategory.HARDWARE,
    )
    """For VALIDATION errors when Storage device name changed before and after test """

    UNSUPPORTED_DUT_ERR = "UNSUPPORTED_DUT_ERR", ErrorCategory.AUTOMATION
    """Error caused by a human accidentally executing a test on an unsupported DUT"""

    RPM_INSTALLATION_FAILED_ERR = "RPM_INSTALLATION_FAILED_ERR", ErrorCategory.TEST_TOOL
    """For errors when rpm was found in repo but installation failed for some reason"""

    RPM_NOT_FOUND_ERR = "RPM_NOT_FOUND_ERR", ErrorCategory.INFRA_TOOL
    """For errors when rpm could not be found in the repo"""

    FS_READ_ONLY_ERR = "FS_READ_ONLY_ERR", ErrorCategory.OS
    """File system is in read only mode error; Usually indicative of automation issues"""

    FS_NO_SPACE_LEFT_ERR = "FS_NO_SPACE_LEFT_ERR", ErrorCategory.OS
    """No space left on device error; Usually indicative of automation issues"""

    CMD_NOT_FOUND_ERR = "CMD_NOT_FOUND_ERR", ErrorCategory.AUTOMATION
    """When command is not found, either due to developer error or when a utility is supposed to be present on the DUT but it is not available, indicating an automation issue"""

    NUMA_NODE_ERR = "NUMA_NODE_ERR", ErrorCategory.HARDWARE
    """For issues related to numa node selection / detection"""

    PERFORMANCE_DEGRADED_ERR = "PERFORMANCE_DEGRADED_ERR", ErrorCategory.HARDWARE
    """For issues related to system / hardware performance"""

    MACHINE_EXTERNAL_INTERRUPT_ERR = (
        "MACHINE_EXTERNAL_INTERRUPT_ERR",
        ErrorCategory.HARDWARE,
    )

    HOST_RECONNECT_ERR = "HOST_RECONNECT_ERR", ErrorCategory.HARDWARE
    """This error type is to be used only in the base AutoVal library where we wait for system to reconnect after reboot/power cycle"""

    HOST_PRE_TEST_HEALTH_CHECK_ERR = (
        "HOST_PRE_TEST_HEALTH_CHECK_ERR",
        ErrorCategory.UNKNOWN,
    )
    """Arbitrary pre-test health check for the DUT failed"""

    SITE_SETTING_ERR = "SITE_SETTING_ERR", ErrorCategory.AUTOMATION
    """ Site setting is not found error """

    # When MAX - MIN iops delta is greater than some threshold (for FIO tests)
    MAX_MIN_IOPS_DELTA_TOO_HIGH_ERR = (
        "MAX_MIN_IOPS_DELTA_TOO_HIGH_ERR",
        ErrorCategory.HARDWARE,
    )

    CONFIGERATOR_ERR = "CONFIGERATOR_ERR", ErrorCategory.AUTOMATION
    """This error type indicates when expected value is not defined in configerator file"""

    LATENCY_ERR = "LATENCY_ERR", ErrorCategory.HARDWARE
    """For high latency errors i.e. when latency does not meet the defined threshold"""
