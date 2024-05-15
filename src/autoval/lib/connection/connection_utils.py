#!/usr/bin/env python3

import sys

from autoval.lib.utils.autoval_log import AutovalLog


class CmdResult:
    def __init__(
        self, command: str, stdout: str, stderr: str, return_code: int, duration: float
    ) -> None:
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.return_code = return_code
        self.duration = duration

    def __str__(self) -> str:
        _this = "Command: %s rc [%d]\n" % (self.command, self.return_code)
        _this += "Output: %s\n" % (self.stdout + self.stderr)
        return _this

    def output(self) -> str:
        return ConnectionUtils.str_encode(self.stdout + self.stderr).strip()


class ConnectionUtils:
    @classmethod
    def log_cmdlog(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        hostname,
        # pyre-fixme[2]: Parameter must be annotated.
        cmd,
        # pyre-fixme[2]: Parameter must be annotated.
        return_code,
        # pyre-fixme[2]: Parameter must be annotated.
        output,
        # pyre-fixme[2]: Parameter must be annotated.
        custom_logfile=None,
    ) -> None:

        cmdlog_msg = "[%s][%s] Exit: %d\n" % (hostname, cmd, return_code)
        if custom_logfile:
            AutovalLog.log_cmdlog(
                cmdlog_msg,
                custom_logfile=custom_logfile,
                custom_logout=output,
            )
        else:
            cmdlog_msg += output
            AutovalLog.log_cmdlog(cmdlog_msg)

    @classmethod
    def str_encode(cls, content: str) -> str:
        if isinstance(content, bytes):
            if sys.version_info[0] < 3:
                content = content.decode("ascii", "ignore")
            else:
                content = str(content, encoding="utf-8", errors="replace")
        if sys.version_info[0] < 3:
            return content.encode("ascii", "ignore")

        return content
