#!/usr/bin/env python3

import os
import queue
import re
import selectors
import socket
import subprocess
import time
from threading import Timer
from typing import List, Optional

import paramiko
from autoval.lib.connection.connection_abstract import ConnectionAbstract
from autoval.lib.connection.connection_utils import CmdResult, ConnectionUtils
from autoval.lib.host.component.component import COMPONENT
from autoval.lib.transport.local import LocalConn
from autoval.lib.utils.autoval_errors import ErrorType
from autoval.lib.utils.autoval_exceptions import CmdError, HostException, TimeoutError

from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.autoval_utils import AutovalUtils
from autoval.lib.utils.decorators import retry
from autoval.lib.utils.site_utils import SiteUtils
from paramiko.agent import AgentClientProxy
from paramiko.channel import Channel
from paramiko.ssh_exception import SSHException


DEFAULT_SUDO_OPTIONS = ["sh", "-lc"]


class SSHResult:
    """
    Result object for all ssh commands
    """

    def __init__(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        return_code,
        stdout: str = "",
        stderr: str = "",
        timed_out: bool = False,
    ) -> None:

        # pyre-fixme[4]: Attribute must be annotated.
        self.return_code = return_code

        # pyre-fixme[4]: Attribute must be annotated.
        self.stdout = ConnectionUtils.str_encode(stdout)

        # pyre-fixme[4]: Attribute must be annotated.
        self.stderr = ConnectionUtils.str_encode(stderr)

        self.timed_out = timed_out


class SSH:
    paramiko_logger_initialized = False

    def __init__(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        host,
        # pyre-fixme[2]: Parameter must be annotated.
        user=None,
        # pyre-fixme[2]: Parameter must be annotated.
        password=None,
        port: int = 22,
        connection_timeout: int = 60,
        allow_agent: bool = True,
        keepalive: int = 0,
    ) -> None:
        if not user:
            user = "root"
        if not SSH.paramiko_logger_initialized:
            AutovalLog.init_paramiko_logger()
            SSH.paramiko_logger_initialized = True
        # pyre-fixme[4]: Attribute must be annotated.
        self._host = host
        # pyre-fixme[4]: Attribute must be annotated.
        self._user = user
        # pyre-fixme[4]: Attribute must be annotated.
        self._password = password
        self._port = port
        # pyre-fixme[4]: Attribute must be annotated.
        self._ssh_key_path = SiteUtils().get_ssh_key_path()
        self._connection_timeout = connection_timeout
        self._allow_agent = allow_agent
        self.keepalive = keepalive
        # Remove the file from the list if it does not exist.
        if self._ssh_key_path:
            for ssh_cert_file in self._ssh_key_path:
                if not os.path.exists(ssh_cert_file):
                    self._ssh_key_path.remove(ssh_cert_file)

    @retry(tries=3, sleep_seconds=30)
    # pyre-fixme[3]: Return type must be annotated.
    def _connect_to_host(self):
        try:
            # pyre-fixme[16]: `SSH` has no attribute `_ssh`.
            self._ssh = paramiko.SSHClient()
            self._ssh.load_system_host_keys()
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._ssh.connect(
                self._host,
                username=self._user,
                password=self._password,
                timeout=self._connection_timeout,
                banner_timeout=120,
                port=self._port,
                key_filename=self._ssh_key_path,
                allow_agent=self._allow_agent,
            )
            if self.keepalive != 0:
                # pyre-fixme[16]: `SSHClient` has no attribute `_transport`.
                self._ssh._transport.set_keepalive(self.keepalive)

        except paramiko.ssh_exception.AuthenticationException:
            raise HostException(
                f"Authentication Failure : Failed to establish ssh connection to {self._host}",
                component=COMPONENT.SYSTEM,
                error_type=ErrorType.NOT_ACCESSIBLE_ERR,
            )

        # pyre-fixme[16]: Module `paramiko` has no attribute `BadHostKeyException`.
        except paramiko.BadHostKeyException:
            # removing old host key and retry
            LocalConn(self._host).run("ssh-keygen -R %s" % self._host)
            raise
        except Exception as e:
            raise HostException(
                "Failed to connect to {}: {}".format(self._host, str(e))
            )
        return

    def _disconnect(self) -> None:
        # pyre-fixme[16]: `SSH` has no attribute `_ssh`.
        if self._ssh:
            self._ssh.close()
            self._ssh = None

    def __enter__(self) -> "SSH":
        # Used for "with"-style connections
        self._connect_to_host()
        return self

    # pyre-fixme[2]: Parameter must be annotated.
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Used for "with"-style connections
        self._disconnect()

    # pyre-fixme[2]: Parameter must be annotated.
    def raise_timeout(self, cmd, timeout, queue) -> None:
        queue.put("SSH command [%s] timed out after [%d] seconds" % (cmd, timeout))
        self._disconnect()


class SSHCommand:
    """
    Run the actual SSH command on an 'SSH' type object
    """

    def __init__(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        ssh,
        # pyre-fixme[2]: Parameter must be annotated.
        cmd,
        timeout: int = 600,
        get_pty: bool = False,
        path_env: Optional[List[str]] = None,
    ) -> None:
        self._timeout = timeout
        # pyre-fixme[4]: Attribute must be annotated.
        self.ssh = ssh
        # pyre-fixme[4]: Attribute must be annotated.
        self._cmd = "".join(cmd)
        self.get_pty = get_pty
        self.path_env = path_env

    def __enter__(self) -> SSHResult:

        return_code = -1
        thread_queue = queue.Queue()
        # Using a timer to disconnect the SSH session once timeout is reached.
        timer = Timer(
            self._timeout,
            self.ssh.raise_timeout,
            [self._cmd, self._timeout, thread_queue],
        )
        try:
            timer.start()
            if self.path_env:
                # Append to existing PATH env
                self._cmd = (
                    "export PATH=$PATH:" + ":".join(self.path_env) + f";{self._cmd}"
                )
            (stdin, stdout, stderr, return_code) = self._exec()
        finally:
            timer.cancel()
            try:
                error = thread_queue.get(block=False)  # noqa
                return_code = 124
            except queue.Empty:
                pass

        return SSHResult(return_code, stdout=stdout, stderr=stderr)

    # pyre-fixme[2]: Parameter must be annotated.
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return

    # pyre-fixme[3]: Return type must be annotated.
    def _exec(self):
        (stdin, stdout, stderr) = self.ssh._ssh.exec_command(
            self._cmd,
            get_pty=self.get_pty,
        )

        # channel is shared for stdin, stdout and stderr
        channel = stdout.channel
        stdout_chunks = []
        stderr_chunks = []

        # since we're not using stdin and nor do we write
        stdin.close()
        channel.shutdown_write()

        # read stdout/stderr in order to prevent read block hangs
        stdout_chunks.append(channel.recv(len(channel.in_buffer)))

        # read chunk-by-chunk to prevent stalls
        # 'channel.closed' checks if channel was closed prematurely,
        # and there is no data in the buffers.
        sel = selectors.DefaultSelector()
        sel.register(channel, selectors.EVENT_READ)
        while not channel.closed or channel.recv_ready() or channel.recv_stderr_ready():
            got_chunk = False
            sel_res = sel.select()
            readq = [v[0].fileobj for v in sel_res if v]
            for c in readq:
                # pyre-fixme[16]: Item `HasFileno` of `Union[HasFileno, int]` has no
                #  attribute `recv_ready`.
                if c.recv_ready():
                    # pyre-fixme[16]: Item `HasFileno` of `Union[HasFileno, int]`
                    #  has no attribute `in_buffer`.
                    stdout_chunks.append(channel.recv(len(c.in_buffer)))
                    got_chunk = True
                # pyre-fixme[16]: Item `HasFileno` of `Union[HasFileno, int]` has no
                #  attribute `recv_stderr_ready`.
                if c.recv_stderr_ready():
                    # make sure to read stderr to prevent stall
                    # pyre-fixme[16]: Item `HasFileno` of `Union[HasFileno, int]`
                    #  has no attribute `in_stderr_buffer`.
                    stderr_chunks.append(channel.recv_stderr(len(c.in_stderr_buffer)))
                    got_chunk = True
            if (
                not got_chunk
                and channel.exit_status_ready()
                and not channel.recv_stderr_ready()
                and not channel.recv_ready()
            ):
                channel.shutdown_read()
                sel.unregister(channel)
                sel.close()
                channel.close()
                break

        stderr.close()
        stdout.close()

        return (
            stdin,
            b"".join(stdout_chunks),
            b"".join(stderr_chunks),
            channel.recv_exit_status(),
        )


class SSHConn(ConnectionAbstract):
    """
    SSH Connection class implementing the ConnectionAbstract abstract base class
    for a common interface between different connection types (Thrift, SSH, ...)
    """

    def __init__(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        host,
        skip_health_check: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        user=None,
        # pyre-fixme[2]: Parameter must be annotated.
        password=None,
        allow_agent: bool = True,
        sudo: bool = False,
    ) -> None:
        # pyre-fixme[4]: Attribute must be annotated.
        self.hostname = host
        self.port = 22
        # pyre-fixme[4]: Attribute must be annotated.
        self.user = user
        # pyre-fixme[4]: Attribute must be annotated.
        self.password = password
        self.allow_agent = allow_agent
        self.sudo = sudo
        self._connect(skip_health_check)
        # pyre-fixme[4]: Attribute must be annotated.
        self._is_root = None

    @property
    # pyre-fixme[3]: Return type must be annotated.
    def is_root(self):
        if self._is_root is None:
            if self.user == "root":
                self._is_root = True
            else:
                self._is_root = False
                groups = self.run_get_result("groups").stdout
                self._is_root = "root" in groups
        return self._is_root

    def _connect(self, skip_health_check: bool = False) -> None:
        # @@@ TODO: ??? What to put here?
        # self.instance = HostAddr(self.hostname, self.port)
        # @@@ TODO: Should check health of connection here unless
        # "skip_health_check" is set
        return

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
        forward_ssh_agent: bool = False,
        path_env: Optional[List[str]] = None,
    ) -> CmdResult:
        """
        SSH.run_get_result() implements the ConnectionAbstract.run abstract base function
        for a common interface between different connection types (Thrift, SSH, ...)

        SSH.run_get_result() does not currently support background.
        """
        #
        if working_directory:
            cmd = "cd %s && %s" % (working_directory, cmd)
        AutovalLog.log_debug(
            f'Running cmd: "{cmd}", timeout: {timeout}, working_directory: {working_directory}'
        )
        key_args = {
            "host": self.hostname,
            "user": self.user,
            "password": self.password,
            "port": self.port,
            "allow_agent": self.allow_agent,
            "connection_timeout": connection_timeout,
            "keepalive": keepalive,
        }
        with SSH(**key_args) as ssh, SSHAgent(
            ssh, forward_ssh_agent=forward_ssh_agent
        ) as ssh_agent:  # noqa
            if sudo or self.sudo:
                options = ""
                if sudo_options is not None:
                    options = " ".join(sudo_options)
                cmd = f"sudo {options} {cmd}"
            if not self.is_root:
                if not path_env:
                    path_env = []
                path_env.extend(["/usr/sbin", "/usr/bin", "/sbin"])
            _cmd = [cmd]
            start_time = time.time()
            with SSHCommand(ssh, _cmd, timeout, get_pty, path_env) as result:

                duration = time.time() - start_time
                _out = result.stdout + result.stderr
                self._log_cmd_metrics(
                    cmd, start_time, duration, result.return_code, _out
                )
                _out = ConnectionUtils.str_encode(_out)
                ConnectionUtils.log_cmdlog(
                    self.hostname, cmd, result.return_code, _out, custom_logfile
                )
                if result.return_code == 124:
                    raise TimeoutError(
                        f"[{cmd}] timed out. Failed to complete within {timeout} seconds on {self.hostname}"
                    )
                if result.return_code != 0 and not ignore_status:
                    msg = "Command returned non-zero exit status on %s" % (
                        self.hostname
                    )
                    if "command not found" in _out:
                        raise CmdError(
                            cmd, result, msg, error_type=ErrorType.CMD_NOT_FOUND_ERR
                        )
                    raise CmdError(cmd, result, msg)
                return CmdResult(
                    cmd,
                    result.stdout,
                    result.stderr,
                    result.return_code,
                    duration,
                )

    # pyre-fixme[3]: Return type must be annotated.
    def ssh_connect(self):
        # Establishes connection to the host

        with SSH(self.hostname, port=self.port, password=self.password) as ssh:
            connect_status = ssh._connect_to_host()
        return connect_status

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def read_file(self, file_path, decode_ascii: bool = False, **kwargs):
        # Reads file_path and returns its contents as string

        with SSH(self.hostname, port=self.port, password=self.password) as ssh:
            try:
                # pyre-fixme[16]: `SSH` has no attribute `_ssh`.
                sftp = ssh._ssh.open_sftp()
                remote_file = sftp.open(file_path)
                content = remote_file.read().rstrip()
                remote_file.close()
                if decode_ascii:
                    content = ConnectionUtils.str_encode(content)
            except Exception as e:
                raise Exception("Failed to read file %s: %s" % (file_path, str(e)))
        return content

    # pyre-fixme[2]: Parameter must be annotated.
    def get_file(self, file_path, target, **kwargs) -> None:
        # Copies file_path from remote system to target on local system

        with SSH(self.hostname, port=self.port, password=self.password) as ssh:
            try:
                # pyre-fixme[16]: `SSH` has no attribute `_ssh`.
                sftp = ssh._ssh.open_sftp()
                sftp.get(file_path, target)
            except Exception as e:
                raise Exception("Failed to get file %s: %s" % (file_path, str(e)))

    # pyre-fixme[2]: Parameter must be annotated.
    def put_file(self, file_path, target, **kwargs) -> None:
        """Transfers local file to remote host over ssh.
        Args:
            file_path: Source file path
            target: target file path
        Returns:
            None

        Raises:
            Exception: if there is a problem in transferring file or source and target checksums do not match
        """
        AutovalLog.log_as_cmd(
            f"Transferring {file_path} to remote host {self.hostname} at {target}"
        )
        AutovalLog.log_debug(
            f"Transferring {file_path} to remote host {self.hostname} at {target}"
        )
        md5sum_cmd_output = AutovalUtils.run_get_output(f"md5sum {file_path}")
        source_file_md5sum = md5sum_cmd_output.split()[0]
        AutovalLog.log_debug(f"Source file md5sum : {source_file_md5sum}")
        with SSH(self.hostname, port=self.port, password=self.password) as ssh:
            try:
                # pyre-fixme[16]: `SSH` has no attribute `_ssh`.
                sftp = ssh._ssh.open_sftp()
                sftp.put(file_path, target)
            except Exception as e:
                raise Exception(
                    f"Failed to transfer source file {file_path} to remote host {self.hostname} at {target}. Reason : {e}"
                )
        md5sum_cmd_result = self.run_get_result(cmd=f"md5sum {target}")
        target_file_md5sum = md5sum_cmd_result.stdout.split()[0]
        AutovalLog.log_debug(f"target file md5sum : {target_file_md5sum}")
        if source_file_md5sum != target_file_md5sum:
            raise Exception(
                "Failed to transfer source file {file_path} to remote host {self.hostname} at {target}. Reason : Source file checksum {source_file_md5sum} and target file checksum {target_file_md5sum} do not match"
            )

    def scp_file(
        self, source_location: str, file_tocopy: str, destination_location: str
    ) -> str:
        # Prefer put_file method to transfer file

        # calculates and validates the checksum of the file
        # and then copies the file from source to destination using scp

        target = self.hostname
        password = self.password
        AutovalLog.log_as_cmd("Copying the required version to the OpenBMC")
        try:
            output = AutovalUtils.run_get_output(
                " md5sum %s/%s" % (source_location, file_tocopy)
            )
            md5sum_before_copy = output.split()[0]
            try:
                cmd = (
                    "sshpass -p '%s' scp -6 -o StrictHostKeyChecking=no"
                    " -o UserKnownHostsFile=/dev/null %s/%s"
                    % (password, source_location, file_tocopy)
                )

                output = AutovalUtils.run_get_output(
                    r"%s root@[\%s\]:%s" % (cmd, target, destination_location)
                )
                append_string = "-6"
            except Exception:
                cmd = (
                    "sshpass -p '%s' scp -o StrictHostKeyChecking=no"
                    " -o UserKnownHostsFile=/dev/null %s/%s"
                    % (password, source_location, file_tocopy)
                )

                output = AutovalUtils.run_get_output(
                    "%s root@%s:%s" % (cmd, target, destination_location)
                )
                append_string = ""
            # after copy check md5sum on the system
            cmd = (
                "sshpass -p '%s' ssh %s -o StrictHostKeyChecking=no"
                " -o UserKnownHostsFile=/dev/null" % (password, append_string)
            )
            output = AutovalUtils.run_get_output(
                '%s root@%s "md5sum %s/%s"'
                % (cmd, target, destination_location, file_tocopy)
            )
            md5sum_after_copy = output.split()[0]

            if str(md5sum_before_copy) not in str(md5sum_after_copy):
                raise Exception("checksum doesnt match, its not safe to proceed")

            AutovalLog.log_as_cmd("checksum matches")
            return file_tocopy
        except Exception as e:
            raise Exception("Failed to scp file %s: %s" % (file_tocopy, str(e)))

    # pyre-fixme[2]: Parameter must be annotated.
    def rsync_file(self, src, dst, quick=None) -> None:
        target = self.hostname
        cmd0 = ""
        cmd1 = ""

        if quick:
            cmd1 += "--ignore-existing "
        cmd1 += "%s root@[%s]:%s" % (src, target, dst)

        try:
            cmd0 = "sshpass -p %s rsync -rzq " % self.password
            AutovalUtils.run_get_output(cmd0 + cmd1)
        except BaseException as e:
            raise Exception("rsync failed %s %s %s : %s" % (src, target, dst, str(e)))

    """
    Purpose:
    Helper function to run commands within the host to the remote machine using sshpass command line utility. This helps to address use cases to detect usb0 access from the DUT
    Params:
    cmd: str Command to run the remote host
    hostname: str hostname/ip address to connect
    user: str username for authentication
    password: str password for authentication
    timeout: int timeout in secs
    pubkey_auth: Bool PubkeyAuthentication for sshpass connection.
    """

    # pyre-fixme[3]: Return type must be annotated.
    def sshpass_run_get_output(
        self,
        cmd: str,
        hostname: str,
        # pyre-fixme[2]: Parameter must be annotated.
        user=None,
        # pyre-fixme[2]: Parameter must be annotated.
        password=None,
        pubkey_auth: bool = False,
        timeout: int = 600,
    ):
        pubkey_auth_value = "yes" if pubkey_auth else "no"
        out = self.run_get_result(
            f"timeout {timeout} sudo sshpass -p {password} "
            "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "
            f"-o PubkeyAuthentication={pubkey_auth_value} "
            f"{user}@{hostname} {cmd}"
        )
        return out.stdout


class SSHAgent:
    """
    Class to invoke ssh agent locally, record SSH_AUTH_SOCK
    and SSH_AGENT_PID. Kill the PID at the end of the session.
    Call SSHAgentForwardRequest to forward the agent to the provided channel session
    """

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def __init__(self, ssh, forward_ssh_agent: bool = False):
        self.forward_ssh_agent = forward_ssh_agent
        # pyre-fixme[4]: Attribute must be annotated.
        self.ssh = ssh
        self._ssh_agent_pid: str = ""
        # pyre-fixme[24]: Generic type `list` expects 1 type parameter, use
        #  `typing.List[<element type>]` to avoid runtime subscripting errors.
        self.id_rsa_path: list = SiteUtils().get_ssh_key_path()
        self._ssh_auth_sock: str = ""
        self.agent_forward_req: Optional[SSHAgentForwardRequest] = None

    def __enter__(self) -> "SSHAgent":
        if not self.forward_ssh_agent:
            return self
        # Run the ssh agent and get the PID and path
        completed_process = subprocess.run(
            ["ssh-agent"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        if completed_process.returncode != 0:
            raise SSHException(
                f"Failed to invoke ssh agent. {completed_process.stdout}"
            )
        ssh_auth = re.search(
            r"SSH_AUTH_SOCK=(.*);\s+export\s+SSH_AUTH_SOCK", completed_process.stdout
        )
        ssh_agent = re.search(r"SSH_AGENT_PID=(\d+);", completed_process.stdout)
        if ssh_auth and ssh_agent:
            self._ssh_auth_sock = ssh_auth.group(1)
            self._ssh_agent_pid = ssh_agent.group(1)
        else:
            raise SSHException("Failed to find SSH_AUTH_SOCK or SSH_AGENT_PID")
        # Add certs to the running agent
        env = os.environ.copy()
        env["SSH_AUTH_SOCK"] = self._ssh_auth_sock
        for path in self.id_rsa_path:
            completed_process = subprocess.run(
                ["ssh-add", path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            if completed_process.returncode != 0:
                raise SSHException(
                    f"Failed to add certs to ssh agent. {completed_process.stdout}"
                )
        # Forward ssh agent on the open channel
        transport = self.ssh._ssh.get_transport()
        if transport is not None:
            self.agent_forward_req = SSHAgentForwardRequest(
                transport.open_session(), self._ssh_auth_sock
            )
            AutovalLog.log_info("SSH Agent invoked and cert forwarded")
        return self

    # pyre-fixme[2]: Parameter must be annotated.
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self.forward_ssh_agent:
            return
        # Closing all connections and threads
        if self.agent_forward_req:
            self.agent_forward_req.close()
        # Killing the agent to make sure socket connection with the ssh-agent closes and
        # all the threads invoked in AgentProxyThread are terminated.
        subprocess.run(["kill", "-9", self._ssh_agent_pid])


class AgentConnectionHandler(AgentClientProxy):
    """
    Subclass of AgentClientProxy which over writes connect method to open
    socket on provided agent path.
    """

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def __init__(self, chanRemote, agent_file_path: str):
        self.agent_file_path = agent_file_path
        super().__init__(chanRemote)

    # @override
    # pyre-fixme[3]: Return type must be annotated.
    def connect(self):
        """
        Method automatically called by ``AgentProxyThread.run``.
        """
        conn = self.get_agent_connection()
        if not conn:
            return
        # pyre-fixme[16]: `AgentConnectionHandler` has no attribute `_conn`.
        self._conn = conn

    def get_agent_connection(self) -> socket.socket:
        if self.agent_file_path:
            conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                conn.connect(self.agent_file_path)
                return conn
            except Exception as ex:
                # probably a dangling env var: the ssh agent is gone
                raise SSHException(f"Failed to create agent connection. {ex}")

        else:
            raise SSHException("No Agent path provided to connect")


class SSHAgentForwardRequest:
    """
    Rewrite AgentRequestHandler to forward ssh agent to provided open ssh channel
    """

    # pyre-fixme[3]: Return type must be annotated.
    def __init__(self, chanClient: Channel, agent_file_path: str):
        # pyre-fixme[4]: Attribute must be annotated.
        self._conn = None
        self.agent_file_path = agent_file_path
        # pyre-fixme[4]: Attribute must be annotated.
        self.__clientProxys = []
        self.__chanC = chanClient
        chanClient.request_forward_agent(self._forward_agent_handler)

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def _forward_agent_handler(self, chanRemote):
        self.__clientProxys.append(
            AgentConnectionHandler(chanRemote, self.agent_file_path)
        )

    # pyre-fixme[3]: Return type must be annotated.
    def __del__(self):
        self.close()

    # pyre-fixme[3]: Return type must be annotated.
    def close(self):
        for p in self.__clientProxys:
            p.close()
