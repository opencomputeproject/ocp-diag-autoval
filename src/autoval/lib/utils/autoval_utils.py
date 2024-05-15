#!/usr/bin/env python3

"""
DISCLAIMER: This file is only here for backwards-compatibility!
All future changes should be done in autoval folder!
"""


import ast
import json
import logging
import os
import pathlib
import re
import shlex

from autoval.lib.utils.autoval_output import AutovalOutput as autoval_output


try:
    import queue
except Exception:
    import Queue as queue  # pyre-fixme
import concurrent
import inspect
import signal
import subprocess
import sys
import time
import traceback
from itertools import zip_longest
from threading import Timer
from typing import List, Optional, Tuple

from autoval.lib.host.component.component import COMPONENT
from autoval.lib.utils.autoval_errors import ErrorType
from autoval.lib.utils.autoval_exceptions import (
    AutoValException,
    CmdError,
    TestError,
    TestStepError,
    TestStepSeverity,
    TimeoutError,
)
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.result_handler import ResultHandler
from autoval.plugins.plugin_manager import PluginManager


# Maximum lines/characters of the test log to be displayed on test summary
MAX_STEP_LINES = 10
MAX_STEP_CHARS = 250
# Maximum number of threads for pool executions
MAX_THREADS = 8


class CmdResult:
    def __init__(
        self,
        command: str = "",
        stdout: str = "",
        stderr: str = "",
        # pyre-fixme[2]: Parameter must be annotated.
        return_code=None,
    ) -> None:
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        # pyre-fixme[4]: Attribute must be annotated.
        self.return_code = return_code

    def __str__(self) -> str:
        _this = "Command: %s rc [%d]\n" % (self.command, self.return_code)
        _this += "Output: %s\n" % (self.stdout + self.stderr)
        return _this


class AutovalUtils:

    # pyre-fixme[4]: Attribute must be annotated.
    _host = None

    _test_step = 1
    _test_stage = "setup"
    # pyre-fixme[4]: Attribute must be annotated.
    _failed_test_steps = []
    # pyre-fixme[4]: Attribute must be annotated.
    _passed_test_steps = []
    # pyre-fixme[4]: Attribute must be annotated.
    _warning_steps = []

    result_handler = ResultHandler()
    # pyre-fixme[4]: Attribute must be annotated.
    components = {
        "ASIC": COMPONENT.ASIC,
        "BIOS": COMPONENT.BIOS,
        "BMC": COMPONENT.BMC,
        "CPU": COMPONENT.CPU,
        "DUT": COMPONENT.SYSTEM,
        "NIC": COMPONENT.NIC,
    }

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def _set_host(cls, host) -> None:
        """
        Local function to be called only from autoval_utils
        This sets the Host to the Given host.
        """
        cls._host = host

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def _get_host(cls):
        """
        Local function to be called only from autoval_utils
        """
        return cls._host

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_host_from_hostname(cls, hostname, hosts):
        """
        Get the Host obj from Hostname
        """
        # traceback.print_stack()
        hostname = hostname.replace(".facebook.com", "")
        for host in hosts:
            if host.hostname.replace(".facebook.com", "") == hostname:
                return host
        raise TestError(
            "{} is not available in the list of hosts scheduled.".format(hostname)
        )

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_host_dict(cls, host):
        # traceback.print_stack()
        return host.host_dict

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def run_on_host(cls, host, function, *args, **kwargs):
        """
        To run a function in the given host,
        instead of the system which is executing the test.
        """
        # traceback.print_stack()
        handler = cls._get_host()
        cls._set_host(host)
        try:
            ret = function(*args, **kwargs)
            return ret
        except Exception:
            raise
        finally:
            cls._set_host(handler)

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def check_and_extract_files_to_host(cls, host, source_binary, dut_dir) -> None:
        # Check if the firmware binaries are already extracted. if not, extract
        # it independent of the compression type i.e .tgz, .tar.gz, .zip etc
        # traceback.print_stack()
        if not host.bios.check_binary_contents(dut_dir):
            remote_module_function = "extract"
            remote_module = "havoc.autoval.lib.utils.generic_utils"
            class_name = "GenericUtils"
            params = [source_binary, dut_dir]
            cls.run_remote_module(
                remote_module,
                remote_module_function,
                params=params,
                class_name=class_name,
                host=host,
            )
            host.bios.check_binary_contents(dut_dir, raise_error=True)

    @classmethod
    def run_remotely(cls) -> bool:
        # traceback.print_stack()
        if cls._host is not None:
            return True
        return False

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def loads_json(cls, _str, msg=None):
        """
        Wrapper for json.loads
        @param:
            _str: string  to convert
            msg: message to raise on failure
        """
        # traceback.print_stack()
        try:
            out = json.loads(_str)
            return out
        except Exception as e:
            msg = "Message: {}. ".format(msg) if msg else ""
            raise TestError(f"JSON load failed of '{_str}', msg: {msg}. Error: {e}")

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def raise_process_timeout(cls, process, cmd, timeout, queue) -> None:
        queue.put("Command [%s] timed out after [%d] seconds" % (cmd, timeout))
        cls.kill_proc_family(process)

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def kill_proc_family(cls, process) -> None:
        # Kill process and all child processes
        sig = signal.SIGKILL
        pids = [process.pid]
        while pids:
            tmp_pid = pids.pop()
            try:
                pids.extend(cls._get_child_procs(tmp_pid))
            except Exception:
                pass
            try:
                os.kill(tmp_pid, sig)
            except Exception:
                pass

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def _get_child_procs(cls, pid):
        cmd = "ps -o pid --ppid %d --noheaders" % (pid)
        out = cls.run_get_output(cmd, timeout=None)
        children = [int(s.strip()) for s in out.split("\n")]
        return children

    @classmethod
    def _run_subprocess(
        cls,
        cmd: str,
        # pyre-fixme[2]: Parameter must be annotated.
        timeout=None,
        background: bool = False,
    ) -> CmdResult:
        cmd = shlex.quote(cmd)
        # pyre-fixme[9]: cmd has type `str`; used as `List[str]`.
        cmd = shlex.split(cmd)
        process = subprocess.Popen(  # noqa
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=pathlib.Path.home(),
        )
        proc_stdout = ""
        proc_stderr = ""

        if background:
            return CmdResult(command=cmd, stdout="", stderr="", return_code=0)

        if timeout is None:
            (proc_stdout, proc_stderr, ret_code) = cls._communicate(process)
        else:
            thread_queue = queue.Queue()
            timer = Timer(
                timeout,
                cls.raise_process_timeout,
                [process, cmd, timeout, thread_queue],
            )
            try:
                timer.start()
                (proc_stdout, proc_stderr, ret_code) = cls._communicate(process)
            finally:
                timer.cancel()
                try:
                    error = thread_queue.get(block=False)
                    raise TimeoutError(error)
                except queue.Empty:
                    pass

        return CmdResult(
            command=cmd, stdout=proc_stdout, stderr=proc_stderr, return_code=ret_code
        )

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def _communicate(cls, process):
        proc_stdout, proc_stderr = process.communicate()
        proc_stdout = proc_stdout.decode("utf-8", "ignore")
        proc_stderr = proc_stderr.decode("utf-8", "ignore")
        return (proc_stdout, proc_stderr, process.returncode)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def _run(
        cls,
        cmd: str,
        get_return_code: bool = False,
        ignore_status: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        timeout=None,
        # pyre-fixme[2]: Parameter must be annotated.
        working_directory=None,
        background: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        custom_logfile=None,
    ):
        if cls.run_remotely():
            """
            As ssh lib will accept timeout as integer
            converting timeout from None
            """
            if timeout is None:
                timeout = 600

            if get_return_code:
                out = cls._host.run_get_result(
                    cmd,
                    ignore_status=ignore_status,
                    timeout=timeout,
                    working_directory=working_directory,
                    custom_logfile=custom_logfile,
                )
            else:
                out = cls._host.run(
                    cmd,
                    ignore_status=ignore_status,
                    timeout=timeout,
                    working_directory=working_directory,
                    custom_logfile=custom_logfile,
                )
            if get_return_code:
                return_code = out.return_code
                _out = out.stdout + out.stderr
                stdout = _out.strip()
            else:
                return_code = 0
                stdout = out

            result = CmdResult(command=cmd, stdout=stdout, return_code=return_code)
            return result
        else:
            return cls._run_local(
                cmd,
                get_return_code=get_return_code,
                ignore_status=ignore_status,
                timeout=timeout,
                working_directory=working_directory,
                background=background,
            )

    @classmethod
    def _run_local(
        cls,
        cmd: str,
        get_return_code: bool = False,
        ignore_status: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        timeout=None,
        # pyre-fixme[2]: Parameter must be annotated.
        working_directory=None,
        background: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        custom_logfile=None,
        hostname: str = "localhost",
    ) -> CmdResult:
        """
        Private method that runs cmd and logs output
        """
        if working_directory:
            cmd = "cd %s && %s" % (working_directory, cmd)

        start_time = time.time()
        out = ""
        ret_code = -1
        try:
            result = cls._run_subprocess(cmd, timeout=timeout, background=background)
            duration = time.time() - start_time
            # pyre-fixme[16]: `CmdResult` has no attribute `duration`.
            result.duration = duration
            out = result.stdout.rstrip() + result.stderr.rstrip()
            ret_code = result.return_code
        except TimeoutError:
            ret_code = 124
            raise
        finally:
            duration = time.time() - start_time
            cls.result_handler.add_cmd_metric(
                cmd, start_time, duration, ret_code, out, hostname
            )
            cmdlog_msg = "[%s][%s] Exit: %d\n" % (hostname, cmd, ret_code)
            if custom_logfile:
                AutovalLog.log_cmdlog(
                    cmdlog_msg, custom_logfile=custom_logfile, custom_logout=out
                )
            else:
                cmdlog_msg += out
                AutovalLog.log_cmdlog(cmdlog_msg)

        if get_return_code:
            # This method already returns the result object, which include
            # return code. We just have to make sure to not throw an Exception
            ignore_status = True

        if ret_code and not ignore_status:
            msg = "Command returned non-zero exit status"
            raise CmdError(cmd, result, msg)

        return result

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def run_get_output(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        cmd,
        ignore_status: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        timeout=None,
        # pyre-fixme[2]: Parameter must be annotated.
        working_directory=None,
        get_return_code: bool = False,
        background: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        custom_logfile=None,
    ):
        """
        Run given cmd with verbose set to False
        Returns stdout of cmd on success, Exception on failure
        """
        # Dont check the folder existence for autotest tests
        if custom_logfile is not None and cls.run_remotely():
            custom_log_path = os.path.join(os.getcwd(), "system_logs")
            custom_logfile = os.path.join(custom_log_path, custom_logfile)
            if not os.path.exists(custom_log_path):
                raise TestError("{} does not exists".format(custom_log_path))

        result = cls._run(
            cmd,
            ignore_status=ignore_status,
            timeout=timeout,
            working_directory=working_directory,
            custom_logfile=custom_logfile,
            get_return_code=get_return_code,
            background=background,
        )

        # if get_return_code is True, result is a tuple
        if get_return_code is True:
            return (result.stdout.rstrip(), result.return_code)

        return result.stdout.rstrip()

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def try_run_get_output(cls, cmd, ignore_status: bool = False):
        """
        Tries to run given cmd with verbose set to False
        Returns stdout of cmd on success, None on failure
        """
        try:
            result = cls._run(cmd, ignore_status=ignore_status)
            return result.stdout.rstrip()
        except Exception as e:
            AutovalLog.log_info("Failure try_run_get_output {}".format(e))
            pass

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def run_remote_module(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        module,
        # pyre-fixme[2]: Parameter must be annotated.
        method,
        # pyre-fixme[2]: Parameter must be annotated.
        params=None,
        # pyre-fixme[2]: Parameter must be annotated.
        class_name=None,
        timeout: int = 600,
        # pyre-fixme[2]: Parameter must be annotated.
        host=None,
    ):
        """
        Runs a module in the validation_utils/modules directory.
        For remote use runs through the host module, otherwise runs locally
        @params
        module - Module of the method to be called
        method - Method to be called
        class_name - Class of the  method to be called
        params - List of Params
        timeout - Time out in sec
        host - Host obj of host to run the function.
        """
        if host is None:
            host = cls._host
        return PluginManager.get_plugin_cls("remote_module_executor").run_remote_module(
            module, method, params, class_name, timeout, host
        )

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    # pyre-fixme[24]: Generic type `list` expects 1 type parameter, use
    #  `typing.List[<element type>]` to avoid runtime subscripting errors.
    def run(cls, hosts, func, *args, max_workers=MAX_THREADS) -> Tuple[List, List]:
        """
        Runs the passed method on the list of hosts provided.
        Returns the tuple of results ans exceptions. If the executed method has no return type
        outputs are returned as None. If the executed method run into exception for any host,
        the exception is returned for the specific host otherwise None.

        Args:
            hosts: list of host objects to perform function on.
            func: function to perform.
            *args: arbitrary keyword arguments to be passed in the method.
            max_workers: max number of threads.

        Returns:
            Tuple of List of results and exceptions if any.
        """
        output = []
        errs = []
        if len(hosts) <= 2:
            AutovalLog.log_debug(f"Running {func.__name__} on hosts serially")
            for host in hosts:
                out = err = None
                try:
                    out = func(host, *args)
                except Exception as e:
                    err = e
                output.append(out)
                errs.append(err)
                AutovalLog.log_debug(
                    f"{func.__name__} {'ran successfully'if not err else 'failed to run'} on {host.hostname}"
                )
        else:
            futures = []
            AutovalLog.log_debug(f"Running {func.__name__} on hosts concurrently")
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                for host in hosts:
                    future = executor.submit(func, host, *args)
                    futures.append(future)
            concurrent.futures.wait(futures)
            for future in futures:
                errs.append(future.exception())
                output.append(None if future.exception() else future.result())
                AutovalLog.log_debug(
                    f"{func.__name__} {'ran successfully' if not future.exception() else 'failed to run'} on {hosts[futures.index(future)].hostname}"
                )
        return (output, errs)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def compare_configs(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        first,
        # pyre-fixme[2]: Parameter must be annotated.
        second,
        # pyre-fixme[2]: Parameter must be annotated.
        difference_allowed=None,
        # pyre-fixme[2]: Parameter must be annotated.
        deviation_allowed=None,
    ):
        """
        Compares 2 configuration dicts.
        Returns a dict of the difference in the 2 dicts

        @param first: First dict
        @param second: Second dict
        @param deviation_allowed: Dict of fields where a deviation is allowed.
                                  Key is fieldname, value is deviation allowed
                                  in percent
        @param difference_allowed: Dict of fields where a difference is allowed
                                   Key is fieldname, value is difference allowed
                                   in count
        @return: dict of difference between first and second
        """
        # traceback.print_stack()
        diff = {}
        # Check for keys in first but not in second or where the values differ
        for key in first:
            if key not in second:
                if not first[key]:
                    error = "%s is missing in end config" % key
                    first[key] = error
                    diff.update({key: [None, first[key]]})
                else:
                    diff.update({key: [first[key], None]})
            else:
                found_diff = False
                if difference_allowed and key in difference_allowed:
                    pct_diff = abs(int(first[key]) - int(second[key]))
                    if pct_diff > int(difference_allowed[key]):
                        found_diff = True
                elif deviation_allowed and key in deviation_allowed:
                    pct_diff = (
                        abs(float(first[key]) - float(second[key]))
                        / float(first[key])
                        * 100
                    )
                    if pct_diff > deviation_allowed[key]:
                        found_diff = True
                    elif pct_diff > 0:
                        AutovalLog.log_info(
                            "Deviation of [%s] within limit of [%f]%%"
                            % (key, deviation_allowed[key])
                        )
                elif first[key] != second[key]:
                    found_diff = True
                if found_diff:
                    diff.update({key: [first[key], second[key]]})
        # Now check for keys in second that are not in first
        for key in second:
            if key not in first:
                if not second[key]:
                    error = "%s is missing in start config" % key
                    second[key] = error
                diff.update({key: [None, second[key]]})
        return diff

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def trim_expected_actual_diffs(cls, expected, actual):
        """
        This function compares the expected/actual data and
        returns only the difference between expected/actual.
            expected/actual valid values are:
                - string, multiline string, list of strings
                - dictionary, list, list of dictionary
                - string representation of list/dict
            Ex:
             - dict
                Exp - {"dmi_type": "16", "no_of_bytes": "23"}
                Act - {"dmi_type": "17", "no_of_bytes": "23"}
                Returns: Exp: {"dmi_type":  "16"}, Act: {"dmi_type": "17"}

             - list of strings
                Exp: ["PCI Supported", "BIOS is upgradeable"]
                Act: ["PCI Supported", "BIOS not upgradeable"]
                Returns:
                 - Exp: ["BIOS is upgradeable"],
                 - Act: ["BIOS not upgradeable"]

             - list of dictionary
                Exp: ['{"a": "1", "b": "2"}, {"x": "1", "y": "2"}']
                Act: ['{"a": "1", "b": "4"}, {"x": "1", "y": "2"}']
                Returns:
                  - Exp: ['{"a": "1", "b": "2"}'],
                  - Actual: ['{"a": "1", "b": "4"}']

             - string (does order comparsion for multiline string)
                Exp: "MB Outlet Temp (0x7) \nMB Outlet Temp (0xD) "
                Act: "MB Outlet Temp (0x5) \nMB Outlet Temp (0xD) "
                Returns:
                  - Exp: "MB Outlet Temp (0x7) "
                  - Actual: "MB Outlet Temp (0x5) "
        """
        # Return if either or both expected/actual is None/empty
        # traceback.print_stack()
        if not expected or not actual:
            AutovalLog.log_debug(
                "Either of expected/actual is empty - expected: {}\nactual: {}".format(
                    expected, actual
                )
            )
            return expected, actual

        try:
            expected_str_repr = False
            actual_str_repr = False
            exp = expected
            act = actual

            # convert string representation of list/dict to list/dict if any.
            if (
                isinstance(expected, str)
                and expected.startswith(("[", "{"))
                and expected.endswith(("]", "}"))
            ):
                expected = ast.literal_eval(expected)
                expected_str_repr = True

            if (
                isinstance(actual, str)
                and actual.startswith(("[", "{"))
                and actual.endswith(("]", "}"))
            ):
                actual = ast.literal_eval(actual)
                actual_str_repr = True

            # Order matching is done only for multiline string and ignored
            # for list, dictionary contents.
            if isinstance(expected, dict) and isinstance(actual, dict):
                exp = dict(set(expected.items()) - set(actual.items()))
                act = dict(set(actual.items()) - set(expected.items()))
            elif isinstance(expected, list) and isinstance(actual, list):
                exp = [item for item in expected if item not in actual]
                act = [item for item in actual if item not in expected]
            else:
                # Does order comparsion for multiline string
                diff = [
                    (exp, act)
                    for exp, act in zip_longest(
                        expected.splitlines(), actual.splitlines()
                    )
                    if exp != act
                ]
                exp = "\n".join([i[0] for i in diff if i[0]])
                act = "\n".join([i[1] for i in diff if i[1]])
        except Exception as err:
            AutovalLog.log_debug(
                "Ignoring invalid values: {}\nexpected: {}\nactual: {}".format(
                    err,
                    # pyre-fixme[61]: `exp` is undefined, or not always defined.
                    exp,
                    # pyre-fixme[61]: `act` is undefined, or not always defined.
                    act,
                )
            )
        # pyre-fixme[61]: `expected_str_repr` is undefined, or not always defined.
        exp = (str(exp) if expected_str_repr else exp) if exp else None
        # pyre-fixme[61]: `actual_str_repr` is undefined, or not always defined.
        act = (str(act) if actual_str_repr else act) if act else None
        return exp, act

    @classmethod
    # pyre-fixme[30]: Pyre gave up inferring some types - function `diff_configs`
    #  was too complex.
    # pyre-fixme[3]: Return type must be annotated.
    def diff_configs(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        first,
        # pyre-fixme[2]: Parameter must be annotated.
        second,
        # pyre-fixme[2]: Parameter must be annotated.
        difference_allowed=None,
        # pyre-fixme[2]: Parameter must be annotated.
        deviation_allowed=None,
        # pyre-fixme[2]: Parameter must be annotated.
        parents=None,
        # pyre-fixme[2]: Parameter must be annotated.
        diffs=None,
    ):
        """
        Compares 2 configuration dicts.
        Returns a list of the difference in the 2 dicts
        This routine is recursive for nested dictionaries.

        @param first: First dict
        @param second: Second dict

        @param deviation_allowed: Dict of fields where a deviation is allowed.
                                  Key is fieldname, value is deviation allowed
                                  in percent
        @param difference_allowed: Dict of fields where a difference is allowed
                                   Key is fieldname, value is difference allowed
                                   in count
        @param - (list) parents - the nested dictionary names above us.
        @params - (list) diffs - the list of diffs we've found already.
        @return: dict of difference between first and second or a list of them
                if we found more than 1.
        """
        # traceback.print_stack()
        # so we can append to them.
        if not diffs:
            diffs = {}
        if not parents:
            parents = []
        missing_key = 'missing_key ("%s")'
        # Check for keys in first but not in second or where the values differ
        for key in first:
            if key not in second:
                parents.append(missing_key % key)
                current_answer = [key, None]
                for parent in parents[::-1]:
                    created_diff = {parent: current_answer}
                    current_answer = created_diff
                parents.pop()
                if not diffs:
                    # pyre-fixme[61]: `created_diff` is undefined, or not always
                    #  defined.
                    diffs.update(created_diff)
                else:
                    # pyre-fixme[61]: `created_diff` is undefined, or not always
                    #  defined.
                    cls.merge_nested_dict(diffs, created_diff, parents)
            else:
                found_diff = False
                if difference_allowed and key in difference_allowed:
                    pct_diff = abs(int(first[key]) - int(second[key]))
                    if pct_diff > int(difference_allowed[key]):
                        found_diff = True
                elif deviation_allowed and key in deviation_allowed:
                    pct_diff = (
                        abs(float(first[key]) - float(second[key]))
                        / float(first[key])
                        * 100
                    )
                    if pct_diff > deviation_allowed[key]:
                        found_diff = True
                    elif pct_diff > 0:
                        AutovalLog.log_info(
                            "Deviation of [%s] within limit of [%f]%%"
                            % (key, deviation_allowed[key])
                        )
                elif first[key] != second[key]:
                    if type(first[key]) is dict and type(second[key]) is dict:

                        if parents is None:
                            new_diff = cls.diff_configs(
                                first[key],
                                second[key],
                                difference_allowed=difference_allowed,
                                deviation_allowed=deviation_allowed,
                                parents=[key],
                                diffs=diffs,
                            )
                            if new_diff and new_diff != diffs:
                                if key not in diffs:
                                    diffs.update(new_diff)
                                else:
                                    diffs[key].update(new_diff)

                        else:
                            parents.append(key)
                            new_diff = cls.diff_configs(
                                first[key],
                                second[key],
                                difference_allowed=difference_allowed,
                                deviation_allowed=deviation_allowed,
                                parents=parents,
                                diffs=diffs,
                            )
                            if key in parents:
                                parents.pop()
                            if new_diff and new_diff != diffs:
                                if key not in diffs:
                                    diffs.update(new_diff)
                                else:
                                    cls.merge_nested_dict(diffs, new_diff, parents)
                    else:
                        found_diff = True

                    if found_diff:
                        expected, actual = cls.trim_expected_actual_diffs(
                            first[key], second[key]
                        )
                        if expected or actual:
                            if parents:
                                # here we reconstruct the multi-nexted dictionary.
                                current_answer = [expected, actual]
                                parents.append(key)
                                for parent in parents[::-1]:
                                    created_diff = {parent: current_answer}
                                    current_answer = created_diff
                                parents.pop()
                                if not diffs:
                                    # pyre-fixme[61]: `created_diff` is undefined,
                                    #  or not always defined.
                                    diffs.update(created_diff)
                                else:
                                    # pyre-fixme[61]: `created_diff` is undefined,
                                    #  or not always defined.
                                    cls.merge_nested_dict(diffs, created_diff, parents)
                            else:
                                diffs.update({key: [expected, actual]})
                        else:
                            found_diff = False

        for key in second:
            if key not in first:
                parents.append(missing_key % key)
                current_answer = [None, key]
                for parent in parents[::-1]:
                    created_diff = {parent: current_answer}
                    current_answer = created_diff
                parents.pop()
                if not diffs:
                    # pyre-fixme[61]: `created_diff` is undefined, or not always
                    #  defined.
                    diffs.update(created_diff)
                else:
                    # pyre-fixme[61]: `created_diff` is undefined, or not always
                    #  defined.
                    cls.merge_nested_dict(diffs, created_diff, parents)
        return diffs

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def merge_nested_dict(cls, diffs, created_diff, parents):
        """
        This function becomes necessary when the diffs and created_diffs are
        nested by multple levels and there is a need to identify at which level the
        dictionary needs to be updated.

        Eg:

        diffs = {'DUT':
                    {'M78N7C5100168':
                        {'general_info':
                            {
                            'kernel': ['4.16.18-160_fbk15_4738_ga8b1aad39863', '']
                            }
                        }
                    }
                }

        created_diff = {'DUT':
                            {'M78N7C5100168':
                                {
                                    'syslog_errors': ['', 'some errors']
                                }
                            }
                        }


        parents = ['DUT', 'M78N7C5100168']

        diffs['DUT']['M78N7C5100168'].update(created_diff['DUT']['M78N7C5100168'])
        diffs
        {'DUT':
            {'M78N7C5100168':
                {
                    'general_info':
                        {
                            'kernel': ['4.16.18-160_fbk15_4738_ga8b1aad39863', '']
                        },
                    'syslog_errors': ['', 'some errors']
                }
            }
        }

        """
        # traceback.print_stack()
        for key in parents:
            if key in diffs and key in created_diff:
                diffs = diffs[key]
                created_diff = created_diff[key]
        return diffs.update(created_diff)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def add_dict_key_prefix(cls, old_dict, prefix):
        # traceback.print_stack()
        new_dict = {}
        for key, value in old_dict.items():
            new_dict["%s%s" % (prefix, key)] = value

        return new_dict

    @classmethod
    def _validate(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        did_pass,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        # pyre-fixme[2]: Parameter must be annotated.
        actual=None,
        # pyre-fixme[2]: Parameter must be annotated.
        expected=None,
        # pyre-fixme[2]: Parameter must be annotated.
        operation=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        # pyre-fixme[2]: Parameter must be annotated.
        on_fail=None,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        msg = AutoValException.truncate(msg)
        if component is None:
            component = COMPONENT.UNKNOWN
        if error_type is None:
            error_type = ErrorType.UNKNOWN

        step = cls.add_test_step_result(
            did_pass,
            msg,
            identifier,
            actual,
            expected,
            operation,
            raise_on_fail,
            warning,
            component,
            error_type,
        )
        _msg = cls._get_validation_msg(
            did_pass,
            msg,
            identifier,
            actual,
            expected,
            operation,
            step,
            warning=warning,
            component=component,
            error_type=error_type,
        )
        if log_on_pass or not did_pass:
            AutovalLog.log_info(_msg, False)
            AutovalLog.log_test_result(_msg)
        args = {
            "did_pass": did_pass,
            "msg": msg,
            "actual": actual,
            "expected": expected,
            "operation": operation,
            "error_type": error_type,
            "step_name": name,
            "verdict": verdict,
            "measurement_name": measurement_name,
        }
        autoval_output.add_test_step(**args)
        if not did_pass:
            if warning:
                cls._warning_steps.append(step)
            else:
                cls._failed_test_steps.append(step)
                if on_fail is not None:
                    on_fail_msg = "On failure processing for '%s'" % msg
                    # pyre-fixme[20]: Argument `components` expected.
                    cls._on_fail(
                        on_fail, on_fail_msg, identifier, raise_on_fail, log_on_pass
                    )
                if raise_on_fail:
                    raise TestStepError(_msg)
        else:
            cls._passed_test_steps.append(step)

    @classmethod
    def _on_fail(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        on_fail,
        # pyre-fixme[2]: Parameter must be annotated.
        msg,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier,
        raise_on_fail: bool,
        log_on_pass: bool,
        components: bool,
    ) -> None:
        if not isinstance(on_fail, list):
            raise TestError("Need on_fail param as a list")
        _funct = on_fail.pop(0)
        cls.validate_no_exception(
            _funct,
            on_fail,
            msg,
            identifier,
            raise_on_fail,
            log_on_pass,
            components,
        )

    @classmethod
    def _get_validation_msg(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        did_pass,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier,
        actual: str,
        expected: str,
        # pyre-fixme[2]: Parameter must be annotated.
        operation,
        # pyre-fixme[2]: Parameter must be annotated.
        step,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
    ) -> str:
        # Get the concise summary of actual and expected diff
        before_len = max(len(str(expected)), len(str(actual)))
        expected, actual = cls._get_expected_actual_snapshot(expected, actual)
        if max(len(str(expected)), len(str(actual))) != before_len:
            AutovalLog.log_info(
                "Showing only partial diff. "
                "Full expected/actual diff is in test_steps."
            )

        actual = cls._get_formatted_msg(actual)
        expected = cls._get_formatted_msg(expected)
        if identifier:
            msg = f"[{identifier}] {msg}"
        msg += " - Actual: [%s]" % (actual)
        if operation:
            msg = msg + " - Validation: [%s]" % (operation)
        msg += " - Expected: [%s]" % (expected)
        if did_pass:
            msg = "PASSED - %s - %s" % (step, msg)
        elif warning:
            msg = "WARNING - %s - %s" % (step, msg)
        else:
            msg = "FAILED - %s - %s" % (step, msg)
        return msg

    @classmethod
    def _get_formatted_msg(cls, msg: str) -> str:
        # If there's a newline in the output add another one to the start and
        # end to make sure message is aligned
        try:
            if "\n" in msg:
                msg = "\n" + msg + "\n"
        except Exception:
            pass

        return msg

    @classmethod
    def validate_condition(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        condition,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        # pyre-fixme[2]: Parameter must be annotated.
        on_fail=None,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        """
        Validates that a condition evaluates to True and logs the specified
        message. Throws an exception if condition is False
        @param condition: Condition to check for True
        @param msg: Message to log
        @return None. Throws exception if condition evaluates to False
        """

        cls._validate(
            bool(condition),
            msg,
            identifier=identifier,
            actual=bool(condition),
            expected=True,
            operation="isTrue",
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    def validate_empty_list(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        validate_list,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        """
        Validates that a given list is empty
        """
        cls._validate(
            len(validate_list) == 0,
            msg,
            identifier=identifier,
            actual=validate_list,
            expected=[],
            operation="isEmptyList",
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    def validate_non_empty_list(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        validate_list,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        """
        Validates that a given list is with at least one element.
        """
        did_pass = isinstance(validate_list, list) and len(validate_list) != 0
        cls._validate(
            did_pass,
            msg,
            identifier=identifier,
            actual=validate_list,
            expected="Non Empty List",
            operation="isNonEmptyList",
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    def validate_equal(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        actual,
        # pyre-fixme[2]: Parameter must be annotated.
        expected,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        """
        Validates that actual equals expected (using '==' operator)
        """
        cls._validate(
            actual == expected,
            msg,
            identifier=identifier,
            actual=actual,
            expected=expected,
            operation="isEqual",
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    def validate_not_equal(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        actual,
        # pyre-fixme[2]: Parameter must be annotated.
        expected,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        cls._validate(
            actual != expected,
            msg,
            identifier=identifier,
            actual=actual,
            expected=expected,
            operation="isNotEqual",
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    def validate_range(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        actual,
        # pyre-fixme[2]: Parameter must be annotated.
        lower_limit,
        # pyre-fixme[2]: Parameter must be annotated.
        upper_limit,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
    ) -> None:
        cls._validate(
            lower_limit <= actual <= upper_limit,
            msg,
            identifier=identifier,
            actual=actual,
            expected=f"Min: {lower_limit}, Max: {upper_limit}",
            operation="isWithinRange",
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
        )

    @classmethod
    def validate_less(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        actual,
        # pyre-fixme[2]: Parameter must be annotated.
        expected,
        # pyre-fixme[2]: Parameter must be annotated.
        msg,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        # pyre-fixme[2]: Parameter must be annotated.
        variance=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        cls._validate_lt_gt_eq(
            actual,
            expected,
            msg,
            "lt",
            identifier,
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            variance=variance,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    def validate_less_equal(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        actual,
        # pyre-fixme[2]: Parameter must be annotated.
        expected,
        # pyre-fixme[2]: Parameter must be annotated.
        msg,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        # pyre-fixme[2]: Parameter must be annotated.
        variance=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        cls._validate_lt_gt_eq(
            actual,
            expected,
            msg,
            "lte",
            identifier,
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            variance=variance,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    def validate_greater(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        actual,
        # pyre-fixme[2]: Parameter must be annotated.
        expected,
        # pyre-fixme[2]: Parameter must be annotated.
        msg,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        # pyre-fixme[2]: Parameter must be annotated.
        variance=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        cls._validate_lt_gt_eq(
            actual,
            expected,
            msg,
            "gt",
            identifier,
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            variance=variance,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    def validate_greater_equal(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        actual,
        # pyre-fixme[2]: Parameter must be annotated.
        expected,
        # pyre-fixme[2]: Parameter must be annotated.
        msg,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        # pyre-fixme[2]: Parameter must be annotated.
        variance=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        cls._validate_lt_gt_eq(
            actual,
            expected,
            msg,
            "gte",
            identifier,
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            variance=variance,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    def validate_type(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        obj,
        # pyre-fixme[2]: Parameter must be annotated.
        obj_type,
        # pyre-fixme[2]: Parameter must be annotated.
        msg,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:

        cls.validate_condition(
            isinstance(obj, obj_type),
            msg,
            identifier=identifier,
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def validate_regex_match(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        regex,  # type - SRE_Pattern object returned from re.compile()
        # pyre-fixme[2]: Parameter must be annotated.
        string,  # type - str string to apply regex to
        msg: str,  # type - str message to raise
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,  # type - Optional[str]
        raise_on_fail: bool = True,  # type - bool
        log_on_pass: bool = True,  # type - bool
        warning: bool = False,  # type - bool
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ):  # return type -  Optional[SRE_Match]
        match = re.search(regex, string)
        did_pass = True if match is not None else False
        cls._validate(
            did_pass,
            msg,
            identifier=identifier,
            actual=did_pass,
            expected=True,
            operation="RegexMatch",
            log_on_pass=log_on_pass,
            raise_on_fail=raise_on_fail,
            warning=warning,
            component=component,
            error_type=error_type,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )
        return match

    @classmethod
    def validate_regex_no_match(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        regex,  # type -  SRE_Pattern object returned from re.compile()
        # pyre-fixme[2]: Parameter must be annotated.
        string,  # type -  str string to apply regex to
        msg: str,  # type - str message to raise
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,  # type - Optional[str]
        raise_on_fail: bool = True,  # type - bool
        log_on_pass: bool = True,  # type - bool
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        match = regex.match(string)
        did_pass = True if match is None else False
        cls._validate(
            did_pass,
            msg,
            identifier=identifier,
            actual=(not did_pass),
            expected=False,
            operation="RegexNotMatch",
            log_on_pass=log_on_pass,
            raise_on_fail=raise_on_fail,
            warning=warning,
            component=component,
            error_type=error_type,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    def _validate_lt_gt_eq(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        actual,
        # pyre-fixme[2]: Parameter must be annotated.
        expected,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        comparison,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        # pyre-fixme[2]: Parameter must be annotated.
        variance=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        if variance is not None:
            expected += variance * (1 if "lt" in comparison else -1)
        if comparison == "lt":
            did_pass = actual < expected
            operation = "isLess"
        elif comparison == "lte":
            did_pass = actual <= expected
            operation = "isLessOrEqual"
        elif comparison == "gt":
            did_pass = actual > expected
            operation = "isGreater"
        elif comparison == "gte":
            did_pass = actual >= expected
            operation = "isGreaterOrEqual"
        else:
            raise TestError("Unsupported comparison %s" % (comparison))

        cls._validate(
            did_pass,
            msg,
            identifier=identifier,
            actual=actual,
            expected=expected,
            operation=operation,
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    def validate_in(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        item,
        # pyre-fixme[2]: Parameter must be annotated.
        container,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        """
        Validates that "item" is "in" "container". This works for items of lists
        as well as substring of strings
        """
        cls._validate(
            item in container,
            msg,
            identifier=identifier,
            actual=item,
            expected=container,
            operation="isIn",
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    def validate_not_in(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        item,
        # pyre-fixme[2]: Parameter must be annotated.
        container,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        """
        Validates that "item" is "not in" "container". This works for items of lists
        as well as substring of strings
        """
        cls._validate(
            item not in container,
            msg,
            identifier=identifier,
            actual=item,
            expected=container,
            operation="isNotIn",
            raise_on_fail=raise_on_fail,
            log_on_pass=log_on_pass,
            warning=warning,
            component=component,
            error_type=error_type,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def validate_no_exception(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        code_ref,
        # pyre-fixme[2]: Parameter must be annotated.
        param_list,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ):
        """
        Validates that executing code_ref does not throw an exception. If an
        exception is thrown the test step is marked as failed and the exception
        is re-raised
        """
        exc = None
        result = None
        exc_str = None
        try:
            result = code_ref(*param_list)
        except Exception as e:
            if isinstance(e, AutoValException):
                component = e.component
                error_type = e.error_type
            exc = type(e).__name__ + ": " + str(e)
            exc_str = str(exc)
            if raise_on_fail:
                raise
        finally:
            cls._validate(
                not exc,
                msg,
                identifier=identifier,
                actual=exc_str,
                expected=None,
                operation="isNotException",
                raise_on_fail=raise_on_fail,
                log_on_pass=log_on_pass,
                warning=warning,
                component=component,
                error_type=error_type,
                name=name,
                verdict=verdict,
                measurement_name=measurement_name,
            )

        if result:
            return result

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def validate_exception(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        code_ref,
        # pyre-fixme[2]: Parameter must be annotated.
        param_list,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        exception_type=None,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier=None,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ):
        exc = None
        result = None
        actual = None
        actual_str = None

        try:
            result = code_ref(*param_list)
        except Exception as e:
            exc = e
            actual = type(exc)
            actual_str = str(actual)
            if not exception_type:
                exception_type = type(exc)

        if not exception_type:
            exception_type = Exception

        raise_on_fail = False
        if exc is None or type(exc) != exception_type:
            raise_on_fail = True

        cls._validate(
            exc and issubclass(type(exc), exception_type),
            msg,
            identifier=identifier,
            actual=actual_str,
            expected=str(exception_type),
            operation="isException",
            raise_on_fail=raise_on_fail,
            warning=warning,
            component=component,
            error_type=error_type,
            name=name,
            verdict=verdict,
            measurement_name=measurement_name,
        )

        if result:
            return result

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def process_nested_diff(cls, diff, key=None, key_str: str = "["):
        """
        sample diff when there is a difference between start and end_config

        {'DUT': {'M78N7C5100168': {'syslog_errors': ['', 'some error']}}}

        this function returns the actual and expected value and the
        differing key rom this nested dict.

        key_str stores the keys in the nested dict as below.

        {'DUT': {'M78N7C5100168': {'syslog_errors':}

        TODO: key_str is not used anywhere yet.
        """
        # traceback.print_stack()
        if isinstance(diff[key], list):
            key_str += str(key) + "]"
            return diff, key, key_str

        elif isinstance(diff[key], dict):
            # this would always be nested dictionary
            _key = list(diff[key].keys())[0]
            key_str += str(key) + " - "
            return cls.process_nested_diff(diff[key], _key, key_str)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def split_nested(cls, config, key, list_=None, parents=None):
        """
        This function is required when the diff it nested.
        When the diff contains multiple diffs in it.
        Eg:

        Validate_empty_diff() can receive a diff as below.
        {'DUT': {'M78N7C5100168':
                    {
                    'general_info':
                        {'kernel': ['4.16.18-160_fbk15_4738_ga8b1aad39863', '']
                        },
                    'syslog_errors': ['', 'some errors']
                    }
                }
        }

        It has two sub diffs.
        diff 1: {'DUT': {'M78N7C5100168':
                            {'general_info':
                                {'kernel': ['4.16.18-160_fbk15_4738_ga8b1aad39863', '']
                                },
                            'syslog_errors': ['', 'some errors']
                            }
                        }
                }
        diff 2: {'DUT': {'M78N7C5100168': {'syslog_errors': ['', 'some errors']}}}

        The function seperates them and returns a list


        """
        # traceback.print_stack()
        if not list_:
            list_ = []

        if not parents:
            parents = []

        if isinstance(config[key], list):
            value = config[key]
            parents.append(key)
            for parent in parents[::-1]:

                dict_ = {parent: value}
                value = dict_
            parents.pop()
            # pyre-fixme[61]: `dict_` is undefined, or not always defined.
            list_.append(dict_)
        elif isinstance(config[key], dict):
            parents.append(key)
            for k in config[key]:
                list_ = cls.split_nested(config[key], k, list_=list_, parents=parents)
                if k in parents:
                    parents.pop()
        return list_

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_concise_step_log(cls, log_line):
        """
        This function trims the log to a concised summary.
        Criteria to determine:-
           - For a multiline string, more than MAX_STEP_LINES
             considered to be huge and the snapshot will display only
             MAX_STEP_LINES.

           - For a string, more than MAX_STEP_CHARS is huge
             and snapshot would display only MAX_STEP_CHARS.

           - Within the limit (< MAX_STEP_LINES lines or
             < MAX_STEP_CHARS) will be returned as is.
        """
        log_line = str(log_line)
        split_line = log_line.split("\n")
        if len(split_line) == 1:
            # Single string
            if len(log_line) > MAX_STEP_CHARS:
                # Characters more than MAX_STEP_CHARS
                curr_len = 0
                max_len = 0
                """
                A list or a dictionary would be considered as
                single string and hence truncating the string till
                a comma delimiter close to MAX_STEP_CHARS.
                """
                while curr_len <= MAX_STEP_CHARS:
                    x = re.search(",", log_line[curr_len:])
                    if not x:
                        break
                    curr_len += x.start() + 1
                    if curr_len <= MAX_STEP_CHARS:
                        max_len = curr_len

                if max_len == 0:
                    max_len = MAX_STEP_CHARS
                log_line = log_line[:max_len]

        elif len(split_line) > MAX_STEP_LINES:
            log_line = "\n".join(split_line[:MAX_STEP_LINES])
        else:
            # Do nothing. Multiline string less than MAX_STEP_LINES
            pass
        return log_line

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def _get_expected_actual_snapshot(cls, expected, actual):
        """
        This function gets the snapshot of expected and actual data
        if it is more than MAX_STEP_CHARS or MAX_STEP_LINES.
        """
        if expected:
            expected = cls.get_concise_step_log(expected)
        if actual:
            actual = cls.get_concise_step_log(actual)
        return expected, actual

    @classmethod
    def validate_empty_diff(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        diffs,
        msg: str,
        raise_on_fail: bool = True,
        log_on_pass: bool = True,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        config_errors=None,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
        name: Optional[str] = None,
        verdict: Optional[str] = None,
        measurement_name: Optional[str] = None,
    ) -> None:
        """
        Validates that the diff passed in is empty. Diff has to have the format
        as created by the compare_configs method in this module. Example:
            diff = AutovalUtils.compare_configs(before_dict, after_dict)
            self.validate_empty_diff(diff, "Check for no diff")
        Creates a separate step for each difference (if any)
        """
        if diffs:
            for key in diffs:
                list_of_diffs = cls.split_nested(diffs, key)
                for _diffs in list_of_diffs:
                    diff, config_key, key_str = cls.process_nested_diff(_diffs, key)

                    # check whether failure is due to order mismatch
                    expected = diff[config_key][0]
                    actual = diff[config_key][1]
                    if (
                        isinstance(expected, str)
                        and isinstance(actual, str)
                        and (
                            sorted(expected.splitlines()) == sorted(actual.splitlines())
                        )
                    ):
                        msg += " fail due to Order Mismatch"
                    err_category = {"component": component, "error_type": error_type}
                    if config_errors:
                        err_category = config_errors.get(key, {}).get(
                            config_key, err_category
                        )
                    cls._validate(
                        False,
                        msg,
                        identifier=key_str,
                        operation="isEmptyDiff",
                        actual=actual,
                        expected=expected,
                        raise_on_fail=False,
                        warning=warning,
                        log_on_pass=True,
                        component=err_category.get("component"),
                        error_type=err_category.get("error_type"),
                    )
                    msg = msg.replace(" fail due to Order Mismatch", "")
            if raise_on_fail and not warning:
                raise TestStepError(msg)
        else:
            cls._validate(
                True,
                msg,
                operation="isEmptyDiff",
                actual={},
                expected={},
                raise_on_fail=raise_on_fail,
                log_on_pass=log_on_pass,
            )

        return

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def to_string(obj):
        # traceback.print_stack()
        """Convert an object to a string"""
        string = obj
        # Convert unicode type (only in Python 2), but not str type
        if isinstance(
            obj, ("".__class__, int, float, bool, type, Exception)
        ) and not isinstance(obj, "".__class__):
            string = str(obj)
        elif isinstance(obj, (list, dict)):
            try:
                string = json.dumps(obj)
            except Exception:
                string = str(obj)
        return string

    @classmethod
    def add_test_step_result(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        did_pass,
        msg: str,
        # pyre-fixme[2]: Parameter must be annotated.
        identifier,
        # pyre-fixme[2]: Parameter must be annotated.
        actual,
        # pyre-fixme[2]: Parameter must be annotated.
        expected,
        # pyre-fixme[2]: Parameter must be annotated.
        operation,
        # pyre-fixme[2]: Parameter must be annotated.
        raise_on_fail,
        warning: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        component=None,
        # pyre-fixme[2]: Parameter must be annotated.
        error_type=None,
    ) -> int:
        """
        Adds the test step information to the result_handler module, which will
        later be added to Hive
        """
        now = time.time()
        path = None
        line = None
        for frame in inspect.stack():
            path = frame[1]
            line = frame[2]
            del frame
            # Skip anything coming from standard libraries
            if (
                path.endswith("autoval.py")
                or path.endswith("autoval_utils.py")
                or path.endswith("test_base.py")
                or path.endswith("validation_test.py")
            ):
                continue
            break
        path = cls.relative_path(path)
        stage = cls.get_test_stage()
        step_number = cls._test_step
        cls._test_step += 1
        if not did_pass and warning:
            msg = "Warning: " + msg

        # Concluding severity of the test step
        severity = TestStepSeverity.UNKNOWN
        if did_pass:
            severity = TestStepSeverity.INFO
        else:
            severity = TestStepSeverity.ERROR
            if warning:
                severity = TestStepSeverity.WARNING
            elif raise_on_fail:
                severity = TestStepSeverity.FATAL

        step_dict = {
            "did_pass": bool(did_pass),
            "msg": msg,
            "step_number": step_number,
            "timestamp_ms": int(now * 1000),
            "identifier": identifier,
            "actual": AutovalUtils.to_string(actual),
            "expected": AutovalUtils.to_string(expected),
            "validation": operation,
            "test_file": path,
            "test_line": line,
            "stage": stage,
            "component": component.value,
            "error_type": error_type.value,
            "error_category": error_type.error_category.value,
            "severity": severity.value,
        }
        cls.result_handler.add_test_step(step_dict)
        return step_number

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_failed_test_steps(cls):
        return cls._failed_test_steps

    @classmethod
    def clear_failed_test_steps(cls) -> None:
        cls._failed_test_steps = []

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_passed_test_steps(cls):
        return cls._passed_test_steps

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_warning_steps(cls):
        return cls._warning_steps

    @classmethod
    def relative_path(cls, path: str) -> str:
        """Given the file path of a havoc test/library, return the relative path
        starting from havoc/

        Args:
            path: Absolute path of the module

        Returns:
            Relative path of the module starting from havoc/
        """
        # traceback.print_stack()
        # Get absolute path even when path is relative and chdir has been used
        if not path.startswith("/"):
            if "havoc/" in sys.path[0]:
                path = os.path.abspath(os.path.join(sys.path[0], path))
        else:
            path = os.path.abspath(path)

        partitions = path.rpartition("havoc/")
        relative_path = os.path.join(partitions[1], partitions[2])
        AutovalLog.log_debug(
            f"Module absolute path: {path}, relative path: {relative_path}"
        )
        return relative_path

    # This function gives first match found with regex passed as argument for
    # given command
    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def run_get_match(cls, reg_ex, cmd):
        # traceback.print_stack()
        output = cls.run_get_output(cmd)
        pattern = re.compile(reg_ex, re.MULTILINE | re.DOTALL)
        match = re.search(pattern, output)
        if match:
            return match.group(1)
        else:
            raise TestError("No match found for cmd %s in output %s" % (cmd, output))

    @classmethod
    def get_test_stage(cls, module: str = "test_base") -> str:
        """
        Returns the lifecycle stage of a test step
        """
        life_cycle_stages = [("setup", module), ("execute", ""), ("teardown", module)]
        frames = inspect.stack()
        for _stage, _module in life_cycle_stages:
            if any(
                _stage == stack_frame.function and _module in stack_frame.filename
                for stack_frame in frames
            ):
                cls._test_stage = _stage
                break
        return cls._test_stage
