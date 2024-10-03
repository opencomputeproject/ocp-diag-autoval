#!/usr/bin/env python3
import getpass
import json
import os
import re
import traceback
from datetime import datetime
from shutil import rmtree

import autoval.lib.utils.autoval_shared_data as av_data
from autoval.lib.utils.autoval_errors import ErrorType
from autoval.lib.utils.autoval_exceptions import AutovalFileNotFound, TestError
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.generic_utils import GenericUtils

REPO_DIR = "autoval/"
RESULTS_DIR = "results/autoval/"


class SiteUtils:
    # pyre-fixme[4]: Attribute must be annotated.
    _site_settings = None
    # pyre-fixme[4]: Attribute must be annotated.
    _log_dirs = {
        "dut_logdir": None,
        "dut_tmpdir": None,
        "control_server_logdir": None,
        "control_server_tmpdir": None,
        "tmpdir": None,
        "resultsdir": None,
        "system_logdir": None,
    }
    # pyre-fixme[4]: Attribute must be annotated.
    repository_dir = None

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def init_logdirs_on_control_server(cls, test_obj) -> None:
        try:
            repo = test_obj.config.get("repository_dir", None)
            if repo:
                cls.repository_dir = repo
            # Create set of Log directories in Control server
            cls.create_control_server_logdirs(
                hostname=test_obj.hostname,
                testname=type(test_obj).__name__,
                test_start_time=test_obj.test_start_time,
            )
            # Check for sharedFS mount in the control server
            # SharedStorage(test.host).check_mount_cs_shared_storage()
            # Create result Directory
            test_obj.resultsdir = cls.create_resultsdir(
                logdir=test_obj.config.get("logdir", None),
                hostname=test_obj.hostname if test_obj.connect_to_host else None,
                testname=type(test_obj).__name__,
                test_start_time=test_obj.test_start_time,
            )
        except Exception:
            AutovalLog.log_info("Failed to create control server log directories.")
            raise
        test_obj.control_server_logdir = cls.get_control_server_logdir()
        test_obj.control_server_tmpdir = cls.get_control_server_tmpdir()
        test_obj.system_log_dir = cls.get_system_logdir()
        test_obj.tmpdir = cls.get_tmpdir()

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def init_logdirs_on_test_host(cls, test_obj) -> None:
        """
        Create log directories in the DUT's
        """
        # Check availability of shared storage
        # SharedStorage(test.host).check_mount_dut_shared_storage()
        # Create set of Log directories in DUT's server
        try:
            cls.create_dut_logdirs(
                test_obj.config.get("logdir", None),
                test_obj.host_objs,
                testname=type(test_obj).__name__,
                test_start_time=test_obj.test_start_time,
            )
            test_obj.dut_logdir = cls.get_dut_logdir()
            test_obj.dut_tmpdir = cls.get_dut_tmpdir()
        except Exception:
            AutovalLog.log_info("Failed to create DUT log directories.")
            raise

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def shared_storage(cls):
        from autoval.lib.utils.file_actions import FileActions

        return FileActions

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_site_yum_repo_name(cls):
        return cls.get_site_setting("yum_repo", raise_error=False)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def load_site_settings(
        cls,
        env_var: str = "SITE_SETTINGS",
        default_name: str = "site_settings.json",
    ):
        """Return specific site setting as dictionary located at
        ../autoval/cfg or the settings json
        file location set in the given env variable
        """
        site_settings_file = ""
        site_settings_env = os.environ.get(env_var, default_name)
        # check if the env var contains a json or a path
        try:
            content = GenericUtils.read_file(site_settings_env)
            loaded_settings = json.loads(content.strip())
            return loaded_settings
        except Exception:
            # do not need to do anything in case of exception
            pass
        AutovalLog.log_debug(f"Site Settings : {site_settings_env}")
        relative_cfg_file_path = os.path.join("cfg/site_settings", site_settings_env)
        site_settings_file = GenericUtils.read_resource_cfg(
            file_path=relative_cfg_file_path
        )
        return site_settings_file

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def create_dut_logdirs(cls, logdir, hosts, testname, test_start_time) -> None:
        # Create tmp dir on all the DUT's under test
        # which will be deleted at the end of the test
        for host in hosts:
            # strip all special characters from hostname
            hostname = GenericUtils.strip_special_chars(host.hostname)
            dir_path = SiteUtils.get_full_path_for_dir(
                cls.get_site_setting("dut_tmpdir"),
                hostname,
                testname,
                test_start_time,
            )
            SiteUtils._create_dut_log_directory("dut_tmpdir", dir_path, host)
            dir_path = SiteUtils.get_full_path_for_dir(
                cls.get_site_setting("dut_logdir"),
                hostname,
                testname,
                test_start_time,
            )
            SiteUtils._create_dut_log_directory("dut_logdir", dir_path, host)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def create_control_server_logdirs(
        cls,
        hostname: str,
        # pyre-fixme[2]: Parameter must be annotated.
        testname,
        test_start_time: float,
    ):
        # Create Log dir on the control server (fbje/controller) which will be
        # archive to resultsdir at the end of the test
        dir_path = SiteUtils.get_full_path_for_dir(
            cls.get_site_setting("control_server_logdir"),
            hostname,
            testname,
            test_start_time,
        )
        SiteUtils._create_controller_log_directory(
            "control_server_logdir", dir_path, hostname
        )
        # Create tmp dir on the control server (fbje/controller) which will be
        # deleted at the end of the test
        temp_dir_path = SiteUtils.get_full_path_for_dir(
            cls.get_site_setting("control_server_tmpdir"),
            hostname,
            testname,
            test_start_time,
        )
        SiteUtils._create_controller_log_directory(
            "control_server_tmpdir", temp_dir_path, hostname
        )
        os.chdir(dir_path)
        return dir_path

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def _create_controller_log_directory(cls, dir_name: str, dir_path: str, host: str):
        """
        control_server_logdir --> Log dir at control server and archived at the
                                  end the test. store any critical data on the
                                  control server.
        control_server_tmpdir --> tmp dir at control server and deleted at the
                                  end the of the test. store non critical data
                                  on the control server.
        """
        if not cls.shared_storage().exists(dir_path):
            cls.make_dir(dir_path)
        cls._log_dirs[dir_name] = dir_path
        return cls._log_dirs[dir_name]

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def _create_dut_log_directory(cls, dir_name: str, dir_path: str, host):
        """
        dut_logdir --> Log dir at DUT and archived at the end the test. Used to
                       store critical data on the test server during test.
        dut_tmpdir --> tmp dir at DUT and deleted at the end of the test.
                       store non critical data on the test server during test
        """
        _dir = cls._dut_make_dir(dir_path, host)
        if not isinstance(cls._log_dirs[dir_name], dict):
            cls._log_dirs[dir_name] = {}
        cls._log_dirs[dir_name].update({host.hostname: _dir})
        return cls._log_dirs[dir_name]

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def _dut_make_dir(cls, path, host):
        cls.shared_storage().mkdirs(path=path, host=host)
        return path

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def make_dir(cls, path, force: bool = False):
        return GenericUtils.create_dir(path, force)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def _get_log_dirs(cls, dir_name=None):
        empty_dir = None
        if dir_name is not None:
            if cls._log_dirs[dir_name]:
                return cls._log_dirs[dir_name]
            else:
                empty_dir = dir_name
        else:
            empty_dir = []
            for directory in cls._log_dirs:
                if not directory:
                    empty_dir.extend(cls._log_dirs)
        if not empty_dir:
            return cls._log_dirs
        raise AutovalFileNotFound(
            "The required log directories do not exist %s" % empty_dir
        )

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def create_resultsdir(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        logdir=None,
        # pyre-fixme[2]: Parameter must be annotated.
        hostname=None,
        # pyre-fixme[2]: Parameter must be annotated.
        testname=None,
        # pyre-fixme[2]: Parameter must be annotated.
        test_start_time=None,
    ):
        tmpdir = "tmpdir"
        resultsdir = "resultsdir"
        system_logdir = "system_logdir"
        if logdir:
            results_dir: str = logdir
        else:
            dir_path = cls.get_full_path_for_dir(
                cls.get_site_setting(resultsdir),
                hostname,
                testname,
                test_start_time,
            )
            results_dir: str = dir_path
        system_logs: str = os.path.join(results_dir, "system_logs")
        autoval_tmpdir: str = os.path.join(results_dir, "autoval_tmpdir")
        cls._log_dirs[resultsdir] = results_dir
        cls._log_dirs[tmpdir] = autoval_tmpdir
        cls._log_dirs[system_logdir] = cls.shared_storage().mkdirs(system_logs)

        # Export resultsdir to pytest
        run_in_pytest = av_data.ctx_pytest_autoval.get()
        if run_in_pytest:
            if av_data.ctx_pytest_autoval_results_type.get() == "manifold":
                data = {"mode": "manifold", "uri": results_dir}
                av_data.ctx_pytest_autoval_results.set(data)

        AutovalLog.log_info("Logging to {}".format(results_dir))
        return cls._log_dirs[resultsdir]

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_critical_services(cls):
        services = cls.get_site_setting("dut_critical_services", raise_error=False)
        if services is not None:
            return services
        return []

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def _push_log_to_resultsdir(cls, log_file) -> None:
        try:
            source_path = os.path.join(cls.get_control_server_logdir(), log_file)
            target_path = os.path.join(cls.get_resultsdir(), log_file)
            cls.shared_storage().copy_from_local(None, source_path, target_path)
            cls.shared_storage().rm(source_path)
        except Exception as ex:

            if isinstance(ex.__cause__, AssertionError):
                # AssertionError is thrown on Hi5 systems
                return
            # added log to understand failure to copy cmdlog.log to manifold.
            AutovalLog.log_info(f"failed to copy {log_file} - {ex}")
            # Failing to copy, Logs will be compressed in the control server log archive

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def _push_log_to_system_logs_dir(cls, log_file) -> None:
        """
        This method copies local log files from control_server_tmpdir to system_logs dir
        """
        try:
            source_path = os.path.join(cls.get_control_server_tmpdir(), log_file)
            target_path = os.path.join(cls.get_resultsdir(), "system_logs", log_file)
            cls.shared_storage().copy_from_local(None, source_path, target_path)
            cls.shared_storage().rm(source_path)
        except Exception as ex:
            AutovalLog.log_info(f"failed to copy {log_file} - {ex}")

    @classmethod
    def _push_cmdlog(cls) -> None:
        """
        This method copies the cmdlog.log file from the control server to the
        results directory under cmdlog .
        """
        try:
            log_files = ["cmdlog.log"]
            pattern = re.compile(r"cmdlog\.log\.(\d{4}-\d{2}-\d{2}-\d{6})(\.gz)?$")
            # append commpressed cmdlog files to the list
            for _file in os.listdir(cls.get_control_server_logdir()):
                match = pattern.match(_file)
                if match:
                    log_files.append(_file)
            for log_file in log_files:
                cls._push_log_to_resultsdir(log_file)
        except Exception as ex:
            AutovalLog.log_info(f"failed to copy cmdlog.log - {ex}")

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def cleanup_log_directories(cls, hosts, connect_to_host: bool = True) -> None:
        """
        dut_logdir --> Log dir at DUT and achieve at the end the test.
        dut_tmpdir --> tmp dir at DUT and deleted at the end of the test.
        control_server_logdir --> Log dir at control server and achieve
                                  at the end the test.
        control_server_tmpdir --> tmp dir at control server and deleted
                                  at the end the test.
        tmpdir --> tmp dir at glusterfs (resultsdir) and deleted
                   at the end the test.
        """
        parent_host = hosts[0]
        _host = parent_host.hostname.replace(".facebook.com", "")
        # Push the logs from control server to the results directory
        cls._push_cmdlog()
        cls._push_log_to_resultsdir("test_results.log")
        if cls.shared_storage().exists(
            os.path.join(cls.get_control_server_tmpdir(), "paramiko.log")
        ):
            cls._push_log_to_system_logs_dir("paramiko.log")
        try:
            control_server_logdir = cls.get_control_server_logdir()
        except Exception:
            AutovalLog.log_info("control_server_log directory does not exist")
        else:
            is_cs_log_empty = cls._is_dir_empty(
                parent_host, control_server_logdir, local=True
            )
            if not is_cs_log_empty:
                cls._archive_to_resultsdir(
                    parent_host,
                    control_server_logdir,
                    "control_server_logs.tgz",
                    local=True,
                )
                cls._delete_dir(control_server_logdir, parent_host, local=True)
        try:
            cls._delete_dir(
                cls.get_site_setting("control_server_tmpdir") + _host,
                parent_host,
                local=True,
            )
        except Exception:
            pass
        # Cleanup DUT log_dirs from all DUT's
        if connect_to_host and cls.get_site_settings().get("cleanup_dut_logdirs", True):
            cls.cleanup_dut_logdirs(hosts)

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def cleanup_dut_logdirs(cls, hosts) -> None:
        for host in hosts:
            try:
                dut_logdir = cls.get_dut_logdir(host.hostname)
            except Exception:
                AutovalLog.log_info("dut_log directory does not exist")
            else:
                is_dut_log_empty = cls._is_dir_empty(host, dut_logdir)
                try:
                    # pyre-fixme[21]: Could not find module
                    #  `autoval.lib.test_utils.system_utils`.
                    from autoval.lib.test_utils.system_utils import get_serial_number

                    # pyre-fixme[16]: Module `test_utils` has no attribute
                    #  `system_utils`.
                    serial_number = get_serial_number("baseboard", host)
                except Exception:
                    AutovalLog.log_info("Unable to get the serial number")
                    serial_number = None
                if not is_dut_log_empty:
                    cls._archive_to_resultsdir(
                        host,
                        dut_logdir,
                        f"dut_logs-{serial_number if serial_number else host.hostname}.tgz",
                    )
                    cls._delete_dir(dut_logdir, host)
            try:
                cls._delete_dir(
                    cls.get_dut_tmpdir(host.hostname),
                    host,
                )
            except Exception:
                pass

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def backup_dut_tmpdir(cls, hosts):
        for host in hosts:
            AutovalLog.log_debug(f"Starting backup of tmpdir for host {host.hostname}")
            try:
                dut_tmpdir = cls.get_dut_tmpdir(host.hostname)
                is_empty = cls._is_dir_empty(host, dut_tmpdir)
                AutovalLog.log_debug(
                    f"{dut_tmpdir} on host {host.hostname} is empty : {is_empty}"
                )
                serial_number = None
                try:
                    from autoval.lib.test_utils.system_utils import get_serial_number

                    # pyre-fixme[16]: Module `test_utils` has no attribute
                    #  `system_utils`.
                    serial_number = get_serial_number("baseboard", host)
                except Exception as ex:
                    AutovalLog.log_debug(
                        f"Unable to get the serial number for host {host.hostname}. Ex: {ex}"
                    )
                if not is_empty:
                    backup = f"dut_tmpdir-{serial_number if serial_number else host.hostname}.tgz"
                    cls._archive_to_resultsdir(
                        host,
                        dut_tmpdir,
                        backup,
                    )
            except Exception as ex:
                AutovalLog.log_info(
                    f"Error occurred in taking backup of tmpdir for host {host} Ex: {ex}"
                )

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def _is_dir_empty(cls, host, dir_path, local: bool = False) -> bool:
        cmd = "ls %s" % dir_path
        if not local:
            ret = host.run_get_result(cmd, ignore_status=True)
            if ret.return_code:
                return True
            if ret.stdout:
                return False
            return True
        try:
            if os.listdir(dir_path):
                return False
            return True
        except OSError:
            return False

    @classmethod
    def _archive_to_resultsdir(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        host,
        # pyre-fixme[2]: Parameter must be annotated.
        dir_to_arc,
        # pyre-fixme[2]: Parameter must be annotated.
        filename,
        local: bool = False,
    ) -> None:
        arc_to = cls.get_resultsdir() + "/" + filename
        archive_dir = "archive"
        filename = os.path.join(archive_dir, filename)
        # create the archive under the tmp dir and exclude that directory. -C option to exlude the directory and tar only the contents
        cmd = f"mkdir {archive_dir} && tar -cvzf {filename} --exclude={archive_dir} -C {dir_to_arc} ."
        if local:
            temp_dir = cls.get_control_server_tmpdir()
            host.localhost.run(cmd, working_directory=temp_dir)  # noqa
            _host = None
        else:
            temp_dir = cls.get_dut_tmpdir(host.hostname)
            host.run(cmd, working_directory=temp_dir)  # noqa
            _host = host
        cls.shared_storage().copy_from_local(
            _host, os.path.join(temp_dir, filename), arc_to
        )

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def _delete_dir(cls, dir_path: str, host, local: bool = False) -> None:
        cmd = "rm -rf %s" % dir_path
        if local:
            if cls.shared_storage().exists(dir_path):
                rmtree(dir_path)
            else:
                cls.shared_storage().rm(dir_path)
        else:
            host.run(cmd)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_full_path_for_dir(cls, path, hostname, testname, test_start_time: float):
        _host = hostname.replace(".facebook.com", "") if hostname is not None else ""
        _date = datetime.fromtimestamp(test_start_time).strftime("%Y-%m-%d_%H-%M-%S")
        _full_path = os.path.join(path, _host, testname, _date)
        return _full_path

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_log_dirs(cls):
        return cls._get_log_dirs()

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_tmpdir(cls):
        return cls._get_log_dirs(dir_name="tmpdir")

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_resultsdir(cls):
        return cls._get_log_dirs(dir_name="resultsdir")

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_dut_tmpdir(cls, hostname=None):
        if hostname:
            return cls._get_log_dirs(dir_name="dut_tmpdir")[hostname]
        return cls._get_log_dirs(dir_name="dut_tmpdir")

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_control_server_tmpdir(cls):
        return cls._get_log_dirs(dir_name="control_server_tmpdir")

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_dut_logdir(cls, hostname=None):
        # traceback.print_stack()
        if hostname:
            return cls._get_log_dirs(dir_name="dut_logdir")[hostname]
        return cls._get_log_dirs(dir_name="dut_logdir")

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_control_server_logdir(cls):
        return cls._get_log_dirs(dir_name="control_server_logdir")

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_data_plugins(cls):
        try:
            # pyre-fixme[6]: For 2nd argument expected `bool` but got `None`.
            return cls.get_site_setting("data_plugin", None)
        except TestError:
            return False

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_system_logdir(cls):
        return cls._get_log_dirs(dir_name="system_logdir")

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_site_setting(cls, name, raise_error: bool = True):
        """
        This function retrieves given setting from the site settings.
        Args:
            name (str): The name of the setting to retrieve.
            raise_error (bool, optional): Whether or not to raise an error if the setting is not found. Defaults to True.
        Returns:
            Any: The value of the setting.
        Raises:
            TestError: If the setting is not found and raise_error is set to True.
        """
        if not cls._site_settings:
            cls._site_settings = cls.load_site_settings()
        setting = cls._site_settings.get(name, None)
        if setting is None and raise_error:
            raise TestError(
                f"Site setting {name} not found", error_type=ErrorType.SITE_SETTING_ERR
            )
        return setting

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_site_settings(cls):
        if not cls._site_settings:
            cls._site_settings = cls.load_site_settings()
        return cls._site_settings

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def _get_repository_dir(cls):
        if cls.repository_dir:
            return cls.repository_dir
        site_settings = cls.get_site_settings()
        repository_dir: str = site_settings.get("repository_dir", REPO_DIR)
        return repository_dir

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_golden_config_path(cls):
        repo = cls._get_repository_dir()
        return os.path.join(repo, "golden_config")

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_firmware_path(cls):
        repo = cls._get_repository_dir()
        return os.path.join(repo, "bin")

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_upick_path(cls):
        """
        This function retrieves the upick path from the site settings.
        Returns:
            str: The upick path.
        Raises:
            TestError: If the upick_path is not found in the site settings.
        """
        return cls.get_site_setting("upick_path", raise_error=True)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_tool_path(cls):
        repo = cls._get_repository_dir()
        return os.path.join(repo, "tools")

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_ssh_key_path(cls):
        key_path = None
        try:
            key_path = cls.get_site_setting("ssh_key_path")
            key_path = [
                key.replace("USERNAME", getpass.getuser()) for key in key_path if key
            ]
        except Exception:
            pass
        return key_path

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_plugin_config_path(cls):
        plugin_config_default_path = r"plugins/plugin_config.json"
        plugin_config_path = None
        try:
            plugin_config_path = cls.get_site_setting("plugin_config_path")
        except BaseException:
            pass
        return (
            plugin_config_path
            if plugin_config_path is not None
            else plugin_config_default_path
        )

    @classmethod
    def get_test_utils_plugin_config_path(cls) -> str:
        plugin_config_default_path = r"plugins/test_utils_plugin_config.json"
        plugin_config_path = None
        try:
            plugin_config_path = cls.get_site_setting("test_utils_plugin_config_path")
        except BaseException:
            pass
        return (
            plugin_config_path
            if plugin_config_path is not None
            else plugin_config_default_path
        )
