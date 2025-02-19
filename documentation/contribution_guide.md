```markdown
# Contribution Guide for Autoval OSS

This guide explains how to create a test from scratch using the AutoVal OSS framework, detailing the steps, required imports, class structure, and key components.

## Writing a Test in Autoval OSS

### 1. Basics of Writing a Test

AutoVal OSS is designed to ensure modular, reusable, and portable tests. Every test in AutoVal:

- Inherits from a base class (e.g., `TestBase` or specialized classes like `SSDTestBase`).
- Follows a predefined lifecycle: `Setup`, `Execution`, `Cleanup`.
- Utilizes helpers and validators for streamlined development.

### 2. Test Class Structure

Your test class must inherit from `TestBase` (or a specialized base class like `SSDTestBase` for SSD-related tests). This ensures consistency in setup, execution, and cleanup phases.

```python
class AutoValTest(TestBase):
    """Test description here."""
    def __init__(self, *args, **kwargs):
        super(AutoValTest, self).__init__(*args, **kwargs)

    def setup(self):
        # Perform setup tasks
        super(AutoValTest, self).setup()
        # Add any test specific setup steps needed after the super method is called.

    def execute(self):
        # Test logic and validators go here.

    def cleanup(self):
        # Cleanup resources
        super(AutoValTest, self).cleanup()
        # Add any test specific cleanup steps needed after the super method is called.
```

### 3. Test Lifecycle

AutoVal tests adhere to a strict lifecycle:

- `Setup`: Prepare the environment (e.g., verify connectivity, initialize resources).
- `Execution`: Perform the actual test operations.
- `Cleanup`: Release resources and record results.

Why Use `super().setup()` and `super().cleanup()`?

- `super().setup()` ensures that the test base class's setup tasks are executed (e.g., logging, initializing shared utilities).
- `super().cleanup()` executes post-test cleanup steps defined in the test base class, including error handling and result recording.

### 4. Required Imports

To begin writing a test, you need to import the necessary modules:

#### TestBase Class

**Module:** `from autoval.lib.test_base import TestBase`

- **Description:** The `TestBase` class provides the structure and lifecycle for a test. All tests must inherit from `TestBase`.
- **Lifecycle Methods:**
  - **setup:** Called before test execution to set up the environment, initialize variables, and prepare the system for testing.
  - **execute:** Contains the actual test logic, performing actions to validate the test scenario.
  - **teardown:** Called after test execution to clean up the environment, release resources, and restore the system to its original state.
- **Test Arguments Handling:** The `TestBase` class handles test arguments through the `test_args` attribute, allowing custom arguments to be passed to tests for flexibility and reusability.

#### Example Usage

```python
from autoval.lib.test_base import TestBase

class MyTest(TestBase):
    def setup(self):
        # Set up the environment
        self.log_info("Setting up the environment")

    def execute(self):
        # Perform the test logic
        self.log_info("Executing the test")

    def teardown(self):
        # Clean up the environment
        self.log_info("Tearing down the environment")
```

### AutovalUtils Library

**Module:** `from autoval.lib.utils.autoval_utils import AutovalUtils`

- **Description:** The `AutovalUtils` library leverages several open-source libraries for data manipulation and validation, ensuring the AutoVal framework can handle a wide range of testing scenarios. It allows testers to focus on high-level test logic without worrying about data handling complexities.
- **Example Function:** `validate_condition` verifies if a condition is true.

#### Example Usage

```python
from autoval.lib.utils.autoval_utils import AutovalUtils

system_info = AutovalUtils.get_system_info(host)
self.validate_condition(
    system_info.get("cpu_count") > 4,
    "CPU count is sufficient"
)
```

### COMPONENT Enum

**Module:** `from autoval.lib.host.component.component import COMPONENT`

- **Description:** The `COMPONENT` enum represents system components used for validation.
- **Enum Members:**
  - **BMC:** Baseboard Management Controller
  - **SSD:** Solid State Drive
  - **SYSTEM:** Represents the overall system, used for holistic validations.

In this example, we identify the BMC component using the COMPONENT enum and store it in the `bmc_component` variable. We then use this variable to validate the BMC configuration.

#### Example Usage

```python
from autoval.lib.host.component.component import COMPONENT

# Identify the BMC component
bmc_component = COMPONENT.BMC

# Use the identified component for validation
self.validate_no_exception(
    host.run,
    ["ipmitool", "lan", "print"],
    f"Validated {bmc_component} configuration",
)
```

### ErrorType Enum

**Module:** `from autoval.lib.utils.autoval_errors import ErrorType`

- **Description:** Defines error types used in validation and error handling during tests.

#### Example Usage

```python
self.validate_no_exception(
    host.run,
    ["hostname"],
    "Connected to host",
    component=COMPONENT.SYSTEM,
    error_type=ErrorType.NOT_ACCESSIBLE_ERR,  # Logs an error if the host is not accessible
)
```

### 5. Using Validators

Validators ensure that operations meet expectations. Common validation methods include:

- `self.validate_no_exception`: Checks that an operation completes without exceptions.
- `self.validate_condition`: Verifies that specific conditions are met.
- `self.validate_equal`: Validates that actual equals expected (using `==` operator).
- `self.validate_non_empty_list`: Validates that a given list has at least one element.
- `self.validate_in`: Validates that "item" is "in" "container".

Example of Validators:
```python
# Validate a command runs without errors
self.validate_no_exception(
    host.run,
    ["ls", "/var/log"],
    "Log directory accessible",
    component=COMPONENT.SYSTEM,
    error_type=ErrorType.NOT_ACCESSIBLE_ERR,
)

# Validate a condition
self.validate_condition(
    len(log_files) > 0,
    "Log files are present in the directory"
)
```

### 6. Error Handling with `ErrorType`

Error handling is used for categorization of specific error types for a test failure. These error types will be displayed in the logs generated by autoval.

Common Error Types (`error_types`):

- `ErrorType.NOT_ACCESSIBLE_ERR`: Used when a system or component is unreachable.
- `ErrorType.POST_TEST_CONFIG_VALIDATION_ERR`: For errors related to post-test config validation failure.
- `ErrorType.CMD_TIMEOUT_ERR`: For command timeout errors.

Example:
```python
try:
    self.validate_no_exception(
        host.run,
        ["hostname"],
        "Connected to host",
        component=COMPONENT.SYSTEM,
        error_type=ErrorType.NOT_ACCESSIBLE_ERR,
    )
except Exception as e:
    self.log_error(f"Validation failed: {e}")
```

### 7. Running Commands on Remote Hosts

AutoVal provides a host object for interacting with DUTs. Example operations:

- Run commands: `host.run(command, args)`
- Ping a BMC (host.py): `host.ping_bmc()`

Example:
```python
host.run(["ls", "/tmp"], "Listing temp directory")
```

### 8. Passing Inputs to Tests

Test inputs are defined in a Test Control File (JSON format) and accessed via `self.test_control`.

#### Example JSON:

```json
{
  "iter_count": 10,
  "cycle_type": "ac"
}
```

#### Access in Code:

```python
self.iter_count = self.test_control.get("iter_count", 1)
self.cycle_type = self.test_control.get("cycle_type", "ac")
```

To run an Autoval test with custom test arguments, use the following command:

```
buck-out/v2/gen/fbcode/havoc/autoval/__autoval_test_runner__/autoval_test_runner.par connect.connecttest -s rtptest006.pci6 --args '{"iter_count": 10, "cycle_type": "ac"}'
```

### 9. Writing the Test

#### 9.1 Create the Test Directory

All tests should be stored in the tests directory, see example below:

```
mkdir havoc/autoval/tests/my_cool_autoval_test
```

#### 9.2 Implement the Test

Use the following template to implement your test:

```python
from autoval.lib.test_base import TestBase
from autoval.lib.host.component.component import COMPONENT
from autoval.lib.utils.autoval_errors import ErrorType

class MyCoolAutoValTest(TestBase):
    """
    My custom test for validating a DUT.
    """
    def __init__(self, *args, **kwargs):
        super(MyCoolAutoValTest, self).__init__(*args, **kwargs)

    def setup(self):
        super(MyCoolAutoValTest, self).setup()
        # Additional setup logic
        self.log_info("Setup completed")

    def execute(self):
        # Core test logic
        self.validate_no_exception(
            host.run,
            ["hostname"],
            "Connected to host",
            component=COMPONENT.SYSTEM,
            error_type=ErrorType.NOT_ACCESSIBLE_ERR,
        )
        self.log_info("Execution completed")

    def cleanup(self):
        # Cleanup logic
        super(MyCoolAutoValTest, self).cleanup()
        self.log_info("Cleanup completed")
```

### 10. Additional Considerations

- **Data Collection**:
  - Use `add_config_results` to store configuration data.
    - Used to store hardware and software configuration data in the havoc_system_config table.

  - Use `add_test_results` to store test results.
    - Used to store test outputs in the havoc_result table.

#### Example:

```python
self.add_config_results({
    "cpu_count": 8,
    "memory_size": "16GB",
})

self.add_test_results({
    "disk_read_speed": "500MB/s",
    "test_status": "Pass",
})
```

- **Multithreading**: Use `AutovalThread` for multithreaded operations.
  - Autoval supports multithreaded operations using the AutovalThread utility. This is helpful when parallelizing tasks, such as interacting with multiple DUTs simultaneously.

#### Example:

```python
from autoval.lib.utils.autoval_thread import AutovalThread

# Create a new thread
thread = AutovalThread(target=my_function)

# Start the thread
thread.start()
```

- **Logging**:
  - Use `self.log_info`, `self.log_warning`, or `self.log_error` for structured logging.
- **Environment Variables**:
  - Export required variables before running tests:

  ```
  export HAVOC_SITE_SETTINGS=site_settings_devserver.json
  ```

### 11. Directory Structure

After setting up your test, the directory structure should look like this:

```
autoval/
  tests/
    autoval_test/
      autoval_test.py
      minimal_settings.json
      README.rst
```

### 12. Running the Test

Run your test using the appropriate runner command. Ensure your `SITE_SETTINGS` and environment are correctly configured. Follow the existing documentation for building and running Autoval tests.

For more details, refer to the [Autoval Core Documentation](https://github.com/opencomputeproject/ocp-diag-autoval/blob/dev/documentation/autoval_core.md).
```
