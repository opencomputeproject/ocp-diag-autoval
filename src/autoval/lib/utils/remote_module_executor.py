import os

from autoval.lib.utils.autoval_exceptions import TestError
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.autoval_utils import AutovalUtils

SITE_SETTINGS = "SITE_SETTINGS"


class RemoteModuleExecutor:
    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def run_remote_module(module, method, params, class_name, timeout, host):
        base = "/usr/facebook/"
        module_runner = "autoval.lib.utils.autoval_module_runner"

        # Create cli using --module, -f, -c and --params which refers to
        # which function (-f) in a class (-c) within python file (--module)
        # autoval_module_runner will run passing parameters --params.
        _cli = "python3 -m {} --module {} -f {}".format(module_runner, module, method)
        site_setting = os.environ.get(SITE_SETTINGS, None)
        if site_setting:
            _cli = f"{SITE_SETTINGS}='{site_setting}' {_cli}"
        if class_name is not None:
            _cli += " -c {}".format(class_name)
        if params is not None:
            param_str = " ".join(str(param) for param in params)
            _cli += " --params {}".format(param_str)
        if host is None:
            raise TestError("No Host set/passed to run_remote_module()")
        ret = host.run_get_result(
            _cli,
            working_directory=base,
            timeout=timeout,
        )
        if ret.return_code:
            AutovalLog.log_info(ret.stderr)
        data = ret.stdout.rstrip()
        output = {}
        # Output expected to be either a json data or None
        # don't fail if no data available
        if not data:
            AutovalLog.log_info(f"Remote Runner: {method} - Data not avialable")
        else:
            # Escape any special characters (tab space, newline, carriage return)"
            data = data.replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
            output = AutovalUtils.loads_json(data, method)
        return output
