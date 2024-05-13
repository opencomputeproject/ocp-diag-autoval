#!/usr/bin/env python3
import abc
import time
from typing import List, Optional

from autoval.lib.connection.connection_utils import CmdResult
from autoval.lib.host.component.component import COMPONENT
from autoval.lib.utils.autoval_errors import ErrorType
from autoval.lib.utils.autoval_exceptions import AutoValException, HostException
from autoval.lib.utils.autoval_utils import AutovalLog
from autoval.lib.utils.decorators import retry
from autoval.lib.utils.folder_utils import FolderTransfer
from autoval.lib.utils.result_handler import ResultHandler


class ConnectionAbstract(abc.ABC):
    result_handler = ResultHandler()

    def run(
        self,
        cmd: str,
        ignore_status: bool = False,
        timeout: int = 600,
        working_directory: Optional[str] = None,
        custom_logfile: Optional[str] = None,
        get_pty: bool = False,
        sudo: bool = False,
        sudo_options: Optional[List[str]] = None,
        connection_timeout: int = 60,
        background: bool = False,
        keepalive: int = 0,
        forward_ssh_agent=False,
        path_env: Optional[List[str]] = None,
    ) -> str:
        res = self.run_get_result(
            cmd,
            ignore_status,
            timeout,
            working_directory,
            custom_logfile,
            get_pty,
            sudo,
            sudo_options,
            connection_timeout,
            background,
            keepalive,
            forward_ssh_agent=forward_ssh_agent,
            path_env=path_env,
        )
        return res.output()

    @abc.abstractmethod
    def run_get_result(
        self,
        cmd: str,
        ignore_status: bool = False,
        timeout: int = 600,
        working_directory: Optional[str] = None,
        custom_logfile: Optional[str] = None,
        get_pty: bool = False,
        sudo: bool = False,
        sudo_options: Optional[List[str]] = None,
        connection_timeout: int = 60,
        background: bool = False,
        keepalive: int = 0,
        forward_ssh_agent: bool = False,
        path_env: Optional[List[str]] = None,
    ) -> CmdResult:
        """
        Implemented by SSHConn, ThriftConn, and LocalConn
        Not all paramaters are supported by all connection types.
        """
        pass

    @abc.abstractmethod
    def read_file(self, file_path, **kwargs):
        return

    @abc.abstractmethod
    def get_file(self, file_path, target, **kwargs):
        return

    @abc.abstractmethod
    def put_file(self, file_path, target, **kwargs):
        return

    @abc.abstractmethod
    def scp_file(
        self, source_location: str, file_tocopy: str, destination_location: str
    ) -> str:
        return

    @abc.abstractmethod
    def _connect(self):
        return

    def _log_cmd_metrics(self, cmd, start_time, duration, status, output) -> None:
        self.result_handler.add_cmd_metric(
            cmd, start_time, duration, status, output, self.hostname
        )

    def get_folder(
        self,
        file_path,
        target,
        create: bool = True,
        overwrite: bool = True,
        verbose: bool = False,
    ) -> None:
        """
        Get a remote folder.

        Params:
            file_path (str):
                The path to the remote folder.
            target (str):
                The local folder destination to copy the files to.
            create (bool, optional):
                If true, creates the dest folder if possible.
            overwrite (bool, optional):
                If true, will overwrites the file. True by default.
        Returns:
            None
        """

        xfer = FolderTransfer(
            self, local_path=target, remote_path=file_path, verbose=verbose
        )
        xfer.transfer_from_remote(create=create, overwrite=overwrite)

    def put_folder(
        self,
        file_path,
        target,
        create: bool = True,
        overwrite: bool = True,
        verbose: bool = False,
    ) -> None:
        """
        Put a local folder onto a remote host.

        Params:
            file_path (str):
                The path to the local folder.
            target (str):
                The remote destination to copy the files to.
            create (bool, optional):
                If true, creates the dest folder if possible.
            overwrite (bool, optional):
                If true, will overwrites the file. True by default.
        Returns:
            None
        """
        xfer = FolderTransfer(
            self, local_path=file_path, remote_path=target, verbose=verbose
        )
        xfer.transfer_to_remote(create=create, overwrite=overwrite)

    def reconnect(self, timeout: float = 600) -> None:
        # Reconnects to host. Retries for 'timeout' seconds.
        AutovalLog.log_info("Reconnecting to %s..." % self.hostname)
        end = time.time() + timeout
        success = False
        while time.time() < end:
            try:
                self._connect()
                self.run("/bin/true", timeout=10)
            except Exception:
                time.sleep(10)
                continue
            else:
                success = True
                AutovalLog.log_info("reconnect successful")
                break

        if not success:
            raise Exception(
                "Failed to reconnect to %s after %d seconds" % (self.hostname, timeout)
            )

    def get_last_reboot(self) -> str:
        cmd = "expr `date +%s` - `cut -f1 -d. /proc/uptime`"
        out = self.run(cmd)
        return out

    def has_rebooted(self, prev_reboot_time, new_reboot_time) -> bool:
        if abs(int(prev_reboot_time) - int(new_reboot_time)) > 5:
            return True
        else:
            return False

    @retry(tries=120, sleep_seconds=10, exceptions=(HostException))
    def wait_for_reconnect(self, timeout: float = 1200) -> None:
        self.reconnect(timeout=10)

    def _is_system_booted(self, start_time, shutdown_timeout) -> None:
        system_down = False
        count = 0
        while time.time() < start_time + shutdown_timeout:
            try:
                self.reconnect(timeout=30)
                # For AC and DC cycle, reconnnect wait/retries for more then
                # 1 min and return connection once system reboot is complete.
                if count == 0:
                    if time.time() > start_time + shutdown_timeout:
                        system_down = True
                    count += 1
            except Exception:
                system_down = True
                break
        if not system_down and count != 0:
            raise Exception(
                "System did not start to shutdown with the power cycle command "
                "even after 100 sec"
            )

    @property
    def hostname(self):
        return self._hostname

    @hostname.setter
    def hostname(self, value):
        self._hostname = value
