#!/usr/bin/env python3
from typing import List, Optional

from autoval.lib.connection.connection_abstract import ConnectionAbstract
from autoval.lib.connection.connection_utils import CmdResult, ConnectionUtils
from autoval.lib.utils.autoval_errors import ErrorType
from autoval.lib.utils.autoval_exceptions import CmdError
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.autoval_utils import AutovalUtils
from autoval.lib.utils.file_actions import FileActions

DEFAULT_SUDO_OPTIONS = ["sh", "-lc"]


class LocalConn(ConnectionAbstract):
    def __init__(self, host, sudo: bool = False) -> None:
        self.host = "localhost"
        self.hostname = host
        self.sudo = sudo
        self._is_root = None

    @property
    def is_root(self):
        if self._is_root is None:
            self._is_root = False
            groups = self.run_get_result("groups").stdout
            self._is_root = "root" in groups
        return self._is_root

    def run_get_result(
        self,
        cmd: str,
        ignore_status: bool = False,
        timeout: int = 600,
        working_directory: Optional[str] = None,
        custom_logfile: Optional[str] = None,
        get_pty: bool = False,
        sudo: bool = False,
        sudo_options: Optional[List[str]] = DEFAULT_SUDO_OPTIONS,
        connection_timeout: int = 60,
        background: bool = False,
        keepalive: int = 0,
        forward_ssh_agent: bool = False,  # Not supported by LocalConn
        path_env: Optional[List[str]] = None,
    ) -> CmdResult:
        """
        LocalConn.run_get_result() implements the ConnectionAbstract.run abstract base function
        for a common interface between different connection types (Thrift, SSH, ...)

        LocalConn.run_get_result() does not currently support get_pty.
        LocalConn.run_get_result() does not currently support connection_timeout.
        LocalConn.run_get_result() does not currently support keepalive
        """
        if sudo or self.sudo:
            options = ""
            if sudo_options is not None:
                options = " ".join(sudo_options)
            cmd = f"sudo {options} {cmd}"
        if path_env:
            # Append to existing PATH env
            cmd = "export PATH=$PATH:" + ":".join(path_env) + f";{cmd}"
        AutovalLog.log_debug(
            f'Running cmd: "{cmd}", timeout: {timeout}, working_directory: {working_directory}'
        )
        result = AutovalUtils._run_local(
            cmd,
            get_return_code=True,
            ignore_status=True,
            timeout=timeout,
            working_directory=working_directory,
            background=background,
            custom_logfile=custom_logfile,
            hostname=self.hostname,
        )
        output = f"{result.stdout} {result.stderr}"
        if result.return_code and not ignore_status:
            msg = "Command returned non-zero exit status"
            if "command not found" in output:
                raise CmdError(cmd, result, msg, error_type=ErrorType.CMD_NOT_FOUND_ERR)
            raise CmdError(cmd, result, msg)

        return CmdResult(
            cmd,
            result.stdout,
            result.stderr,
            result.return_code,
            # pyre-fixme[16]: `CmdResult` has no attribute `duration`.
            result.duration,
        )

    def _connect(self) -> None:
        # Nothing to be done here
        return

    def read_file(self, file_path, decode_ascii, **kwargs):
        # Reads file_path and returns its contents as string
        try:
            content = FileActions.read_data(file_path, json_file=False)
            if decode_ascii:
                content = ConnectionUtils.str_encode(content)
        except Exception as e:
            raise Exception("Failed to read file %s: %s" % (file_path, str(e)))
        return content

    def get_file(self, file_path, target, **kwargs) -> None:
        FileActions.copy_tree(file_path, target)

    def put_file(self, file_path, target, **kwargs) -> None:
        FileActions.copy_tree(file_path, target)

    def scp_file(
        self, source_location: str, file_tocopy: str, destination_location: str
    ) -> str:
        raise NotImplementedError()
