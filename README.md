# What is AutoVal?
AutoVal is a test runner framework. The goal of AutoVal is to provide validation functionality and helpful utilities for the hardware validation tests. AutoVal supports running tests on single or multiple hosts.

# Key framework components
This section describes the fundamental AutoVal framework components, and their role in running, validating, and managing a test.
`TestBase` is the abstract and parent class of all tests in AutoVal. `TestBase` initiates and manages the test execution lifecycle.

## Test lifecycle
Test execution lifecycle consists of three phases.
- [Setup](#setup)
- [Execute](#execute)
- [Cleanup](#cleanup)

### Setup
During this stage, `TestBase` performs the following steps.
- Creates log directories
- Initializes the test inputs such as test control arguments, hosts config
- Verifies if the DUT is reachable
- Initiates background monitors according to the test control file settings

### Execute
During this stage, `TestBase` executes the test case. The test-specific code execution starts by `execute()` method. This method must be implemented by all test cases that inherit from `TestBase`.

### Cleanup
During this stage, `TestBase` releases resources and performs test cleanup activities such as deleting temporary log directories, compressing additional test logs, and storing data in the results directory.
If the test case fails, cleanup will call a method `on_fail()`

# Autoval Validation Methods
AutoVal provides validation methods to check the pass/fail status of the test during the test execution. Each test applies a validation method and results in either a Pass or a Fail. A test that consists of test steps should use at least one, but preferably multiple steps to log its status. The system logs the results to the test output and to the test_steps.json file that contains the detailed validation information. The AutoVal validation methods are similar to the Python unit test assert* statements, but they generate additional data that can later be aggregated and analyzed across multiple test runs.

## `validate_condition`
The most basic validation method is `validate_condition`. It takes the following input:
- `condition` (required):  any type of statement that can be evaluated as a boolean.
 If this condition evaluates to `True`, then the corresponding test step is considered a Pass, otherwise a Fail

## Parameters common to all validation methods
Here is the list of parameters available for all validation methods:

| Parameter      | Qualifier | Default | Description |
|----------------|-----------|---------|-------------|
| `msg`          | Required  | N/A     | To print a message as part of the test step output. Since the message is printed for both the Pass and the Fail cases, it should be neutral. |
| `identifer`    | Optional  | `None`  | An additional data field can be logged to specify a particular item under validation. We can use it later for grouping test steps by the same identifier. |
| `raise_on_fail`| Optional  | `True`  | If `True`, a failed validation will raise an exception, which, if not handled, will cause the test to immediately proceed to the cleanup step. If `False`, the test step will still be logged as failed, but testing will continue. |
| `log_on_pass`  | Optional  | `True`  | If `True`, the system will print the test step output in both a Pass and a Fail case. If `False`, the output will not be logged in the Pass case. It reduces the test output for repetitive test steps in the case of a pass. |
| `on_fail`      | Optional  | `None`  | To pass in a code reference that will be executed when the validation results are a Fail. |

## List of validation methods
In addition to `validate_condition()`, there are additional, more specialized methods that can be used by test authors to implement pass/fail criteria. They include the following:
- `validate_empty_list`m `validate_non_empty_list`
- `validate_empty_diff`
- `validate_equal`, `validate_less`, `validate_less_equal`, `validate_greater`, `validate_greater_equal`
- `validate_type`
- `validate_regex_match`, `validate_regex_no_match`
- `validate_in`
- `validate_exception`, `validate_no_exception`
# Test Control
Test Control files are methods to pass inputs to the test. While scheduling an autoval tests users can provide test control file using `--test_control` argument.
# Result Logging
When a test run completes, the test logs data in key/value pairs which are stored in a JSON file.
The `TestBase` class instantiates a `self.result_handler` object that has the following methods to add/update the test results:

| Method                | Description |
| --------------------- | ----------- |
| `add_test_results`    | takes a dictionary with key/value pairs as input that will be added to the `test_results` structure.  |
| `update_test_results` | takes a dictionary with key/value pairs as input that will be updated in the existing test_results. |

The difference with `add_test_results` is that it won’t overwrite existing data, but instead will append an existing list or a previously saved dictionary.

Example:
``` python
result_dict = {"latency": latency_value, "bandwidth": bandwidth_value}
self.result_handler.add_test_results(result_dict)
```
All data added through the `result_handler` object is saved to the `test_results.json` file in the test log directory at the end of the test.

