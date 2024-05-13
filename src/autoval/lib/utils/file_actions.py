#!/usr/bin/env python3
import csv
import json
import os
import stat
from random import sample
from shutil import copyfile, copytree
from string import ascii_lowercase
from typing import Any, Dict, IO, List, Optional, Union

import pkg_resources

from autoval.lib.connection.connection_abstract import ConnectionAbstract
from autoval.lib.utils.autoval_errors import ErrorType
from autoval.lib.utils.autoval_exceptions import (
    AutoValException,
    AutovalFileError,
    AutovalFileNotFound,
    NotSupported,
)
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.autoval_utils import AutovalUtils
from autoval.lib.utils.generic_utils import GenericUtils
from autoval.lib.utils.site_utils import SiteUtils
from autoval.plugins.plugin_manager import PluginManager

from iopath.common.file_io import g_pathmgr

FS_RETRY_LIMIT = 6
FS_SLEEP_TIME = 2


def _exc_handler(func):
    """
    Decorate an object method.
    If method call raises, calls "_handle_exception" on same object with the caught exception.
    The "_handle_exception" method is assumed to exist.
    """

    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            self._handle_exception(e)

    return wrapper


class FileActions:
    @classmethod
    def get_path_manager(cls):
        """Returns pathmanager plugin or g_pathmgr if plugin does not exist"""

        path_manager_plugin = PluginManager.get_plugin_cls("path_manager")
        if path_manager_plugin:
            path_manager = path_manager_plugin().get_path_manager()
        else:
            path_manager = g_pathmgr
        return path_manager

    @staticmethod
    def _run_remote_module(
        host: ConnectionAbstract, method: str, params: List, timeout: int = 600
    ) -> Any:
        out = AutovalUtils.run_remote_module(
            module="havoc.autoval.lib.utils.file_actions",
            method=method,
            class_name="FileActions",
            timeout=timeout,
            host=host,
            params=params,
        )
        return out

    @classmethod
    @_exc_handler
    def mkdirs(cls, path: str, host: Optional[ConnectionAbstract] = None) -> str:
        """
        Recursive directory creation function on a shared location
        @path path - Directory to mkdir
        @host - Host to make directory, Default to control server
        """
        # Create Local Directory
        if host is not None:
            host.run(f"mkdir -p {path}")
        else:
            cls.get_path_manager().mkdirs(path)
        return path

    @classmethod
    @_exc_handler
    def rm(cls, path: str, host: Optional[ConnectionAbstract] = None) -> str:
        """
        Remove directory function from a shared location
        @path path - Directory to remove
        """
        # delete Local Directory
        if host is not None:
            host.run(f"rm -rf {path}")
        else:
            cls.get_path_manager().rm(path)
        return path

    @classmethod
    @_exc_handler
    def glob(
        cls,
        path: str,
        limit_500: bool = False,
    ) -> List[str]:
        """
        Glob a directory tree and return every file (not directory) found in
        it with the full path to the file.
            @path path - Directory to start
            Returns - a list of the files it found.

            Note: not for host mode.
            Manifold doesn't tell us about directories or files.
            Directories you can query for more files, you get an exception if
            you do that with a file.
            So that's how we find the directories to search and the files to return.
        """
        done = False

        files_list = []
        dir_list = []
        dir_list.append(path)

        while not done:
            if dir_list:
                working_path = dir_list.pop(0)
                AutovalLog.log_debug(f"Popped directory {working_path}")
            else:
                done = True
                continue

            files = cls.get_path_manager().ls(working_path)
            for file in files:
                try:
                    new_path = working_path + "/" + file
                    cls.get_path_manager().ls(new_path)
                    dir_list.append(new_path)
                except Exception:
                    # new path is file.
                    # pyre-fixme[61]: `new_path` may not be initialized here.
                    AutovalLog.log_debug(f"Adding file {new_path}")
                    # pyre-fixme[61]: `new_path` may not be initialized here.
                    files_list.append(new_path)
                    if limit_500:
                        if len(files_list) >= 500:
                            return files_list

        return files_list

    @classmethod
    @_exc_handler
    def ls(
        cls,
        path: str,
        dir_only: bool = False,
        host: Optional[ConnectionAbstract] = None,
    ) -> List[str]:
        """
        list function from a shared location
        @path path - Directory to list
        @param host - to perform list contents in the given host
        """
        files = []
        if host is not None:
            if dir_only:
                _dirs = host.run("ls -d", working_directory=path, ignore_status=True)
                if _dirs:
                    files = _dirs.split("\n")
            else:
                _file = host.run(f"ls {path}")
                if _file:
                    files = _file.split("\n")
        else:
            if dir_only:
                raise NotSupported("dir_only option not supported")
            files = cls.get_path_manager().ls(path)
        return files

    @classmethod
    @_exc_handler
    def file_open(cls, file_path: str, mode: str) -> Union[IO[str], IO[bytes]]:
        """
        get the file pointer of the given file
        @path path - Directory to list
        """
        return cls.get_path_manager().open(file_path, mode)

    @classmethod
    @_exc_handler
    def write_data(
        cls,
        path: str,
        contents: Any,
        append: bool = False,
        host: Optional[ConnectionAbstract] = None,
        csv_write_header: bool = False,
        csv_write_rows: bool = False,
        sync: bool = False,
    ) -> None:
        """
        Write data to the sharedFS
        @param path - Path to write Data
        @parm contents - contents to write
        @parm append - True to append data
        @param host - to perform local file write on the goiven host
        @param cvs_write - to perform a csv write.
        """
        remote_path = ""
        mode = "a" if append else "w"
        if host is not None:
            remote_path = path
            tmp_file = "autoval_" + "".join(sample(ascii_lowercase, 8))

            path = os.path.join(SiteUtils.get_control_server_tmpdir(), tmp_file)
            if append and cls.exists(remote_path, host):
                host.get_file(remote_path, path)
        with cls.get_path_manager().open(path, mode) as f:
            if csv_write_header:
                cpu_write = csv.writer(f)
                cpu_write.writerow(contents)
            elif csv_write_rows:
                cpu_write = csv.writer(f)
                cpu_write.writerows(contents)
            elif isinstance(contents, dict) or isinstance(contents, list):
                json.dump(contents, f, indent=4, sort_keys=True)
            else:
                f.write(contents)
        if host is not None:
            cls.rm(remote_path, host)
            host.put_file(path, remote_path)
            cls.rm(path)
            if sync:
                # Run sync if you anticipate the system to be unstable, or the storage device to become
                # suddenly unavailable, and you want to ensure all data is written to disk.
                host.run(f"sync {remote_path}")

    @classmethod
    @_exc_handler
    def read_data(
        cls,
        path: str,
        json_file: bool = False,
        csv_file: bool = False,
        list_data: bool = False,
        csv_reader: bool = False,
        host: Optional[ConnectionAbstract] = None,
        **kwargs,
    ) -> Union[str, Any]:
        """
        Read  data from the sharedFS or local file system
        @param path - File path to read
        @param json_file - True to return Dict
        @param csv_file - True to return CSV data
        #param csv_reader - True to return CSV data from csv_reader.
        @param list_data  - True to return list data
        @param host  - Set Host to read from the given host
        """
        contents = ""
        if host is not None:
            remote_path = path
            tmp_file = "autoval_" + "".join(sample(ascii_lowercase, 8))
            path = os.path.join(SiteUtils.get_control_server_tmpdir(), tmp_file)
            AutovalLog.log_debug(f"path from {path} ")
            if cls.exists(remote_path, host):
                host.get_file(remote_path, path)
        try:
            with cls.get_path_manager().open(path, "r", **kwargs) as fp:
                if json_file:
                    contents = fp.read().strip()
                    contents = json.loads(contents)
                elif csv_file:
                    csv_data = csv.DictReader(fp)
                    contents = list(csv_data)
                elif csv_reader:
                    csv_data = csv.reader(fp)
                    data = []
                    for row in csv_data:
                        data.append(row)
                    contents = data
                elif list_data:
                    contents = [line.strip() for line in fp.readlines()]
                else:
                    contents = fp.read().strip()

        except Exception as e:
            if "Path not found" in str(e):
                raise AutovalFileNotFound(str(e))
            else:
                raise AutovalFileError(str(e))
        if host is not None:
            cls.rm(path)
        return contents

    @classmethod
    def read_resource_file(cls, file_path: str, module: str = "autoval") -> Dict:
        """This function reads the resource json config file and returns the dictionary.
        If the file does not exist, it raises FileNotFoundError

        Assume that we want to read a file located at autoval/cfg/site_settings/site_settings.json,
        To read this file, caller can call this API as below
        read_resource_file(file_path="cfg/site_settings/site_settings.json", module="autoval")

        Args:
            file_path: The relative file path from the module directory
            module: The module name. It must be a valid python package.

        Returns:
            Resource config file content

        Raises:
            FileNotFoundError: If resource config file does not exist
        """
        absolute_file_path = cls.get_resource_file_path(file_path, module=module)

        if os.path.exists(absolute_file_path):
            with open(absolute_file_path) as cfg_file:
                return json.load(cfg_file)
        else:
            raise FileNotFoundError(f"Config file {absolute_file_path} does not exist")

    @staticmethod
    def get_resource_file_path(file_path: str, module=None) -> str:
        """This function returns the absolute path of config file.
        If the file path does not exist, it raises exception

        Assume that we want to get full path a file located at autoval/cfg/site_settings/site_settings.json,
        To read this file, caller can call this API as below
        get_resource_file_path(file_path="cfg/site_settings/site_settings.json", module="autoval")

        Args:
            file_path: The relative file path from the module directory
            module: The module name. It must be a valid python package.

        Returns:
            Resource config file full path
        """

        package = module
        if module is None:
            package = ".".join(
                __name__.split(".")[: __name__.split(".").index("autoval") + 1]
            )
        absolute_file_path = pkg_resources.resource_filename(package, file_path)
        AutovalLog.log_debug(
            f"Relative path from {module}: {file_path}, Resolved absolute resource cfg file path: {absolute_file_path}"
        )
        return absolute_file_path

    @classmethod
    @_exc_handler
    def get_local_path(
        cls,
        host: Optional[ConnectionAbstract],
        remote_path: str,
        force: bool = False,
        recursive: bool = False,
        local_path: Optional[str] = None,
        timeout_sec: float = 600,
    ):
        """
        Function to download and cache the remote file
        @param host - Host to get data to a remote DUT
        @param host - LocalHost or None to get data to control server
        @param remote_path -Remote path to fetch
        @param force -  Forcefully overwrite
        @param recursive - Get a directory contents locally
        @param local_path - get local copy in this dir
        @param timeout_sec - max get local copy operation timeout
        """

        return_path = None
        if host is not None:
            if local_path:
                cache_dir = local_path
            else:
                # Copy Contents to dut_tmpdir
                cache_dir = SiteUtils.get_dut_tmpdir(host.hostname)
            """ param = [remote_path, force, recursive, cache_dir, timeout_sec]
            remote_module_timeout = timeout_sec + 180
            return_path = FileActions._run_remote_module(
                host,
                "_get_local_path",
                param,
                timeout=remote_module_timeout,
            )"""
            temp_path = cls._get_local_path(
                remote_path, force, recursive, cache_dir, timeout_sec
            )
            host.put_file(file_path=temp_path, target=local_path)
            return local_path
        else:
            if local_path:
                cache_dir = local_path
            else:
                # Copy Contents to control_server_tmpdir
                cache_dir = SiteUtils.get_control_server_tmpdir()
            return_path = cls._get_local_path(
                remote_path, force, recursive, cache_dir, timeout_sec
            )

        """ if local_path:
            filename = os.path.basename(remote_path)
            if not cls.exists(local_path, host):
                cls.mkdirs(local_path, host)
            dst_path = os.path.join(local_path, filename)
            # copy the file to desired dir
            cls.copy_from_local(host, return_path, dst_path, overwrite=force)
            return_path = dst_path """

        return return_path

    @classmethod
    def _get_local_path(
        cls,
        remote_path: str,
        force: Union[str, bool],
        recursive: Union[str, bool],
        cache_dir: Optional[str],
        timeout_sec: float,
    ) -> str:
        # recursive and cache_dir not supported in local File access
        # Setting strict_kwargs_checking to False to bypass this
        cls.get_path_manager().set_strict_kwargs_checking(False)
        recursive = (
            GenericUtils.strtobool(recursive)
            if isinstance(recursive, str)
            else recursive
        )
        force = GenericUtils.strtobool(force) if isinstance(force, str) else force
        timeout_sec = (
            float(timeout_sec) if isinstance(timeout_sec, str) else timeout_sec
        )
        try:
            ret = cls.get_path_manager().get_local_path(
                remote_path,
                force=force,
                recursive=recursive,
                cache_dir=cache_dir,
                timeout_sec=timeout_sec,
            )
        except Exception as ex:
            raise AutovalFileError(f"Failed to get local path - {ex}")
        return ret

    @classmethod
    @_exc_handler
    def copy_from_local(
        cls,
        host: Optional[ConnectionAbstract],
        local_path: str,
        dst_path: str,
        overwrite: bool = False,
    ) -> str:
        """
        Function to copy a local file to the specified location.
        """
        if host is not None:
            """param = [local_path, dst_path, overwrite]
            return FileActions._run_remote_module(host, "_copy_from_local", param)"""
            path = os.path.join(
                SiteUtils.get_control_server_tmpdir(),
                f"{os.path.basename(local_path)}_tmp",
            )
            host.get_file(file_path=local_path, target=path)
            return cls._copy_from_local(path, dst_path, overwrite=overwrite)
        else:
            return cls._copy_from_local(local_path, dst_path, overwrite)

    @classmethod
    def _copy_from_local(cls, local_path: str, dst_path: str, overwrite: bool) -> str:
        return cls.get_path_manager().copy_from_local(local_path, dst_path, overwrite)

    @classmethod
    @_exc_handler
    def copy(
        cls,
        src_path: str,
        dst_path: str,
        overwrite: bool = False,
        host: Optional[ConnectionAbstract] = None,
    ) -> bool:
        """
        Copy a source path to a destination path.
        Provided source and destination must be there in the same share
        @param src_path - source path to copy
        @param dst_path - Dest path to copy
        @return - status (bool): True on success
        """
        if host is not None:
            if overwrite:
                cmd = f"cp -arf {src_path} {dst_path}"
            else:
                cmd = f"cp -ar {src_path} {dst_path}"
            host.run(cmd)
            ret_val = True
        else:
            ret_val = cls.get_path_manager().copy(src_path, dst_path, overwrite)

        return ret_val

    @classmethod
    @_exc_handler
    def move(
        cls,
        src_path: str,
        dst_path: str,
        host: Optional[ConnectionAbstract] = None,
    ) -> bool:
        """
        Move a source path to a destination path.
        Provided source and destination must be there in the same share
        @param src_path - source path to copy
        @param dst_path - Dest path to copy
        @return - status (bool): True on success
        """
        # delete Local Directory
        if host is not None:
            host.run(f"mv {src_path} {dst_path}")
            ret_val = True
        else:
            ret_val = cls.get_path_manager().mv(src_path, dst_path)
        return ret_val

    @classmethod
    @_exc_handler
    def exists(cls, path: str, host: Optional[ConnectionAbstract] = None) -> bool:
        """
        Checks if there is a resource at the given
        @path path - Path to check
        @host - Host to check directory exist
        """
        exists = False
        if host is not None:
            cmd = f"ls -s {path}"
            ret = host.run_get_result(cmd, ignore_status=True)
            exists = not bool(ret.return_code)
        else:
            exists = cls.get_path_manager().exists(path)
        return exists

    @classmethod
    @_exc_handler
    def extract_files_to_host(
        cls, host: ConnectionAbstract, source_path: str, dest_path: str
    ) -> str:
        """
        Extract file to the given Host
        @param Host - Host object
        @param source_path - Source path of the file to extract
        @param dest_path - Destination to extract
        """
        source_path = cls.get_local_path(host, source_path)
        remote_module_function = "extract"
        remote_module = "havoc.autoval.lib.utils.generic_utils"
        class_name = "GenericUtils"
        params = [source_path, dest_path]
        AutovalUtils.run_remote_module(
            remote_module,
            remote_module_function,
            params=params,
            class_name=class_name,
            host=host,
        )
        return dest_path

    @classmethod
    @_exc_handler
    def add_executable_permission(
        cls, host: Optional[ConnectionAbstract], path: str
    ) -> None:
        if host is not None:
            host.run(f"chmod +x -R {path}")  # noqa
        else:
            st = os.stat(path)
            os.chmod(path, st.st_mode | stat.S_IEXEC)

    @classmethod
    def _handle_exception(cls, exception):
        """
        A handler method for exception handeling
        """
        error_type = ErrorType.STORAGE_SERVICE_ERR
        if "[404] Path not found" in str(
            exception
        ) or "No such file or directory" in str(exception):
            error_type = ErrorType.INPUT_ERR
        elif "Read-only file system" in str(exception):
            error_type = ErrorType.FS_READ_ONLY_ERR
        elif "No space left on device" in str(
            exception
        ) or "No usable temporary directory found" in str(exception):
            error_type = ErrorType.FS_NO_SPACE_LEFT_ERR
        elif "Input/output error" in str(exception):
            error_type = ErrorType.DRIVE_ERR
        raise AutoValException(str(exception), error_type=error_type) from exception

    @classmethod
    def copy_tree(cls, source: str, target: str, create_dir: bool = True) -> None:
        """
        copies whole directory with its contents, does not work for remote locations
        """
        if create_dir and not os.path.isdir(os.path.dirname(os.path.normpath(target))):
            os.makedirs(os.path.dirname(os.path.normpath(target)))
        if os.path.isdir(source):
            copytree(source, target)
        else:
            copyfile(source, target)
