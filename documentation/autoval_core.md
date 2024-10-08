## Background
### AutoVal
AutoVal is a portable test runner framework that was made to validate functionality of server hardware. AutoVal provides tests and libraries to connect and run tests on a server. The tests can run on single or multiple hosts either locally on the hardware under test or remotely.

### Design Principles
It follows three design principles: portable, reusable, and open source-able.

#### Portable
Autoval oss can be run on any DUT (Device Under Test) that is reachable with an IP address. No infrastructure is needed.

#### Reusable
With its modular design, decoupled tests and libraries made for system validation. Autoval allows for ease of writing tests and reusing code to run tests on DUTs.

#### Open source-able
There are github repositories available to the public with a module test design to enable community members to design and contribute to test suites.

## Basic Architecture
The basic architecture of Autoval OSS is as follows:
1. Test Control File
    * This is the main configuration file that defines the test scenario.
    Test-specific parameters are defined here and used alongside tests
2. TestBase class
    * This is the abstract base class that all tests inherit from
    * It provides common functions like setup, execute, teardown, and process_results which are part of the lifecycle that this class dictates for all autoval tests
    * The lifecycle of an autoval test is as follows:
        + Init → Setup → Execution → Cleanup
            + Init: the test initializes essential tools like AutovalLog and AutovalUtils
            + Setup: the pre-test operations take place to check if reachable and prepare for testing
            + Execution: the test case is executed
            + Cleanup: the post-test operations take place to record results and clean up the host
3. Test Cases
    * These are the individual tests that inherit from the TestBase class.
    * They contain the specific test steps and validation logic for each test
4. AutovalUtils
    * These are helper functions and classes that provide additional functionality
        + Host-related data gathering and interactions
        + Methods related to running methods on host(s)
        + Config comparisons
        + Validations
5. ResultHandler
    * This is a class that creates, updates, and prints test results

## Utilities
### AutovalLog
When creating tests for Autoval OSS, AutovalLog will be used to log messages, warnings, and errors during the test lifecycle. It allows developers to track the progress of the tests, identify issues and debug errors. Just like logger library, AutovalLog also allows for different log levels to filter logs to reduce cluttering and prioritize log messages

### SiteUtils
When the test needs to refer to log directories or create them on the DUTs, developers can import SiteUtils and use the functionality of the class to create, retrieve, or even clean-up log directories.

### AutovalUtils
The AutovalUtils class offers a collection of validation methods that can be used throughout the execution of tests. These methods allow the developers to verify that specific conditions are met during the testing process.

## Site Settings
The site settings should be exported once before actually running the tests to allow Autoval modules to pick up correct environment variables.

For example, Autoval SSH modules would require environment variable ssh_key_path to help point it towards the right path to the certificates file

```
{
  "control_server_logdir": "/autoval/logs/",
  "control_server_tmpdir": "/tmp/autoval/",
  "dut_logdir": "/autoval/logs/",
  "dut_tmpdir": "/tmp/autoval/",
  "resultsdir": "/autoval/results/",
  "ssh_key_path": ["/USERNAME/.ssh/id_rsa"],
  "plugin_config_path" : "plugins/plugin_config.json",
  "repository_dir": "/autoval/repository/",
  "test_utils_plugin_config_path" : "plugins/test_utils_plugin_config.json",
  "cleanup_dut_logdirs" : false,
  "yum_repo": "autoval_tools"
}
```

* **control_server_logdir**: the directory where logs from the control server will be stored
* **control_server_tmpdir**: the directory where temporary files from the control server will be stored
* **dut_logdir**: the directory where the logs from the DUTs will be stored
* **resultsdir**: the directory where test results will be stored
* **ssh_key_path**: the path to the SSH key used to connect to the DUT
* **plugin_config_path**: the path to the plugin configuration file
* **repository_dir**: the directory where the Autoval repository is located
* **test_utils_plugin_config_path**: the path to the test utils plugin configuration file
* **cleanup_dut_logdirs**: a boolean value that decides whether to cleanup logdirs from DUT during the cleanup phase after running the test
* **yum_repo**: a custom repository for hosting RPMs (Red Hat Package Managers) used by the tests in autoval SSD repository

In order to make use of the yum repository, follow this guide to install yum repository: https://www.redhat.com/sysadmin/add-yum-repository

To export site settings, put the following command in the terminal used to run tests.

```
export SITE_SETTINGS=src/autoval/cfg/site_settings/site_settings.json
```
