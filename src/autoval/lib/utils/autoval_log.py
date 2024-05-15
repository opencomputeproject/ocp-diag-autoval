#!/usr/bin/env python3

import gzip
import inspect
import logging
import os
import re
import shutil
import sys
import time
from logging.handlers import RotatingFileHandler
from typing import Dict

from autoval.lib.utils.autoval_exceptions import AutovalFileNotFound

from autoval.lib.utils.autoval_output import AutovalOutput as autoval_output


class AutovalLog:
    _logs_initialized = False
    _debug = False
    # pyre-fixme[4]: Attribute must be annotated.
    log_level = logging.INFO
    # pyre-fixme[4]: Attribute must be annotated.
    _version = (
        (float)(sys.version_info[0])
        + (0.1 * (float)(sys.version_info[1]))
        + (0.01 * (float)(sys.version_info[2]))
    )

    # backward compatibility for python version below 3.8 :initializing logging config
    if _version < 3.8:
        logging.basicConfig(
            level=log_level,
            format="[%(asctime)s] - %(message)s",
            datefmt="%m/%d/%Y %H:%M:%S",
        )

    @classmethod
    def set_logging(
        cls,
        console_file_log_enabled: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        filename=None,
        debug: bool = False,
    ) -> None:

        cls._debug = debug

        if cls._version < 3.8 and cls._debug:
            # backward compatibility for python version below 3.8 : setting logging as debug
            cls.set_log_debug()
            return

        log_level = logging.DEBUG if cls._debug else logging.INFO

        # stacklevel arg is available only in python 3.8 and above. Initially enable this in debug log level only.
        log_format = (
            "[%(levelname).1s%(asctime)s %(filename)s:%(lineno)s] %(message)s"
            if cls._debug and cls._version >= 3.8
            else "[%(asctime)s] - %(message)s"
        )
        # if not forced, this method does nothing and logging continue to use old config only
        if console_file_log_enabled and filename:
            # save logs to specified file.
            logging.basicConfig(
                filename=filename,
                filemode="w",
                level=log_level,
                format=log_format,
                datefmt="%m/%d/%Y %H:%M:%S",
                force=True,
            )

            # as well redirect logs to console too.
            console = logging.StreamHandler()
            console.setLevel(log_level)
            formatter = logging.Formatter(log_format)
            console.setFormatter(formatter)
            logging.getLogger("").addHandler(console)

            cls.log_info(
                f"logging setting enabled with options : debug - {cls._debug}, console_file_log_enabled - {console_file_log_enabled}, filename - {filename}"
            )
        else:

            logging.basicConfig(
                level=log_level,
                format=log_format,
                datefmt="%m/%d/%Y %H:%M:%S",
                force=True,
            )

    @classmethod
    def log_cmdlog(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        msg,
        # pyre-fixme[2]: Parameter must be annotated.
        custom_logfile=None,
        # pyre-fixme[2]: Parameter must be annotated.
        custom_logout=None,
    ) -> None:
        cls._log(msg, custom_logfile, custom_logout)

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def log_as_cmd(cls, msg) -> None:
        """
        Add an arbitrary message to the cmd_metrics and cmdlog logfiles
        """
        from autoval.lib.utils.result_handler import ResultHandler

        ResultHandler().add_cmd_metric("log message", time.time(), 0, 0, msg)
        cls.log_cmdlog(msg)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def filter_stacks(cls, stacklevel, previous_frame, current_frame):

        if "run" in current_frame.f_code.co_name and any(
            filename in current_frame.f_code.co_filename
            for filename in [
                "thrift.py",
                "local.py",
                "ssh.py",
                "host.py",
                "connection_abstract.py",
                "autoval_utils.py",
            ]
        ):
            while True:
                if "run" not in current_frame.f_code.co_name:
                    break
                current_frame = previous_frame
                previous_frame = previous_frame.f_back
                stacklevel += 1
            stacklevel -= 1

        # Handeling validation cases (validate_* methods) which are in autoval_utils.py
        if (
            "validate" in current_frame.f_code.co_name
            and "autoval_utils.py" in current_frame.f_code.co_filename
        ):
            while True:
                if (
                    "validate" not in current_frame.f_code.co_name
                    and "autoval_utils.py" not in current_frame.f_code.co_filename
                ):
                    break

                current_frame = previous_frame
                previous_frame = previous_frame.f_back
                stacklevel += 1
            stacklevel -= 1

        # Handeling remote module run
        if "run_remote_module" in current_frame.f_code.co_name:
            while True:
                if "run_remote_module" not in current_frame.f_code.co_filename:
                    break
                current_frame = previous_frame
                stacklevel += 1
                previous_frame = previous_frame.f_back

        return stacklevel

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_stacklevel(cls):

        if cls._version < 3.8:
            return None
        stacklevel = 3

        # pyre-fixme[16]: Optional type has no attribute `f_back`.
        previous_frame = inspect.currentframe().f_back.f_back.f_back
        current_frame = inspect.currentframe().f_back.f_back.f_back

        return cls.filter_stacks(stacklevel, previous_frame, current_frame)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_cmdlog_stacklevel(cls, msg):
        if cls._version < 3.8:
            return None
        stacklevel = 3

        # pyre-fixme[16]: Optional type has no attribute `f_back`.
        previous_frame = inspect.currentframe().f_back.f_back.f_back
        current_frame = inspect.currentframe().f_back.f_back.f_back
        while True:
            if "cmdlog" not in current_frame.f_code.co_name:
                break
            current_frame = previous_frame
            stacklevel += 1
            previous_frame = previous_frame.f_back
        return cls.filter_stacks(stacklevel, previous_frame, current_frame)

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def log_info(cls, msg, ocp_log=False) -> None:
        """
        Placeholder for logging functionality. Currently just uses logging
        module to log.
        @param msg: String to log
        """
        logging.info(**AutovalLog.get_log_args(msg))
        if ocp_log:
            autoval_output.log(severity="INFO", msg=msg)

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def log_debug(cls, msg) -> None:
        """
        Placeholder for logging functionality. Currently just uses logging
        module to log.
        @param msg: String to log
        """

        logging.debug(**AutovalLog.get_log_args(msg))

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def log_warning(cls, msg) -> None:
        """
        Placeholder for logging functionality. Currently just uses logging
        module to log.
        @param msg: String to log
        """
        logging.warning(**AutovalLog.get_log_args(msg))

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def log_error(cls, msg) -> None:
        """
        Placeholder for logging functionality. Currently just uses logging
        module to log.
        @param msg: String to log
        """
        logging.error(**AutovalLog.get_log_args(msg))

    @classmethod
    # pyre-fixme[24]: Generic type `dict` expects 2 type parameters, use
    #  `typing.Dict[<key type>, <value type>]` to avoid runtime subscripting errors.
    def get_log_args(cls, msg: str) -> Dict:
        args = {
            "msg": msg,
            "stacklevel": cls.get_stacklevel(),
        }
        args = {k: v for k, v in args.items() if v is not None}
        return args

    @classmethod
    def set_log_debug(cls) -> None:

        cls.log_level = logging.DEBUG
        logging.getLogger().setLevel(logging.DEBUG)

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def log_test_result(cls, msg) -> None:
        if not cls._logs_initialized:
            cls._init_logs()
        _logger = logging.getLogger("conditions")
        _logger.info(msg)

    @classmethod
    def _log(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        msg,
        # pyre-fixme[2]: Parameter must be annotated.
        custom_logfile=None,
        # pyre-fixme[2]: Parameter must be annotated.
        custom_logout=None,
    ) -> None:
        if not cls._logs_initialized:
            cls._init_logs()

        if custom_logfile and custom_logout:
            message = "Output redirected to %s\n" % custom_logfile
            msg = msg + message
            cls._write_custom_log(custom_logfile, custom_logout)
        _logger = logging.getLogger("cmdlog")

        kwargs = {
            k: v
            for k, v in {
                "msg": msg,
                "stacklevel": cls.get_cmdlog_stacklevel(msg),
            }.items()
            if v is not None
        }

        _logger.info(**kwargs)

    @classmethod
    def _write_custom_log(
        cls,
        custom_logfile: str,
        output: str,
    ) -> None:
        from autoval.lib.utils.file_actions import FileActions
        from autoval.lib.utils.site_utils import SiteUtils

        custom_log_path: str = SiteUtils.get_system_logdir()
        custom_logfile: str = os.path.join(custom_log_path, custom_logfile)
        FileActions().write_data(custom_logfile, output)

    @classmethod
    # pyre-fixme[24]: Generic type `dict` expects 2 type parameters, use
    #  `typing.Dict[<key type>, <value type>]` to avoid runtime subscripting errors.
    def test_control(cls) -> Dict:
        from autoval.lib.test_args import TEST_CONTROL

        return TEST_CONTROL

    @classmethod
    def _init_logs(cls) -> None:
        try:
            from autoval.lib.utils.site_utils import SiteUtils

            resultsdir = SiteUtils.get_resultsdir()
            # Writing log to control_server_logdir
            if os.path.exists(resultsdir):
                log_dir = resultsdir
            else:
                log_dir = SiteUtils.get_control_server_logdir()

        except AutovalFileNotFound:
            log_dir = os.getcwd()

        cmdlog = os.path.join(log_dir, "cmdlog.log")
        test_results = os.path.join(log_dir, "test_results.log")
        cls.log_info(f"Runtime cmdlog location: {cmdlog}")
        _logger = logging.getLogger("cmdlog")
        if cls.test_control().get("disable_log_rotation", False):
            hdlr = logging.FileHandler(cmdlog, encoding="UTF-8")
        else:
            hdlr = RotatingFileHandler(
                cmdlog, encoding="UTF-8", maxBytes=1024 * 1024 * 1024, backupCount=100
            )
            if not cls.test_control().get("disable_compress_log", False):
                hdlr.rotator = cls.gzip_rotator
            hdlr.namer = cls.namer
        formatter = logging.Formatter(
            (
                "[%(levelname).1s%(asctime)s %(filename)s:%(lineno)s] %(message)s"
                if cls._debug and cls._version >= 3.8
                else "[%(asctime)s] - %(message)s"
            ),
            datefmt="%m/%d/%Y %H:%M:%S",
        )
        hdlr.setFormatter(formatter)
        _logger.addHandler(hdlr)
        _logger.setLevel(cls.log_level)
        _logger.propagate = False

        _cond_logger = logging.getLogger("conditions")
        hdlr = logging.FileHandler(test_results, encoding="UTF-8")
        formatter = logging.Formatter(
            (
                "[%(levelname).1s%(asctime)s %(filename)s:%(lineno)s] %(message)s"
                if cls._debug and cls._version >= 3.8
                else "[%(asctime)s] - %(message)s"
            ),
            datefmt="%m/%d/%Y %H:%M:%S",
        )
        hdlr.setFormatter(formatter)
        _cond_logger.addHandler(hdlr)
        _cond_logger.setLevel(logging.INFO)
        _cond_logger.propagate = False

        cls._logs_initialized = True

    @classmethod
    def init_paramiko_logger(cls) -> None:
        # Writing log to
        from autoval.lib.utils.site_utils import SiteUtils

        _logger = logging.getLogger("paramiko")
        paramiko_log = os.path.join(
            SiteUtils.get_control_server_tmpdir(), "paramiko.log"
        )
        cls.log_debug(f"Runtime paramiko log location: {paramiko_log}")
        hdlr = logging.FileHandler(paramiko_log, encoding="UTF-8")
        formatter = logging.Formatter(
            "[%(asctime)s] %(message)s", datefmt="%m/%d/%Y %H:%M:%S"
        )
        hdlr.setFormatter(formatter)
        _logger.addHandler(hdlr)
        _logger.setLevel(logging.INFO)
        _logger.propagate = False

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def namer(cls, name) -> str:
        current_timestamp = time.strftime(
            "%Y-%m-%d-%H%M%S", time.localtime(time.time())
        )
        name = re.sub(r".\d+$", "", name)
        if not cls.test_control().get("disable_compress_log", False):
            return f"{name}.{current_timestamp}.gz"
        else:
            return f"{name}.{current_timestamp}"

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def gzip_rotator(cls, source, dest) -> None:
        AutovalLog.log_info(
            f"cmdlog.log size has been reached 1 GB limit, compressed and rotated as {os.path.basename(dest)}"
        )
        with open(source, "rb") as f_in:
            with gzip.open(dest, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(source)
