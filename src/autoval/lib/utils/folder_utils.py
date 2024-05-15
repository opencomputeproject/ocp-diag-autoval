import pathlib
import time

from autoval.lib.utils.autoval_exceptions import (
    FolderTransferError,
    FolderTransferErrorCodes as fec,
)
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.autoval_utils import AutovalUtils


class FolderTransfer:

    REMOTE_PREFIX = "/tmp/remote_folderxfer"
    LOCAL_PREFIX = "/tmp/local_folderxfer"

    def __init__(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        remote_conn,
        *,
        local_path: str,
        remote_path: str,
        verbose: bool = False,
    ) -> None:
        """
        Create a Folder Transfer Object

        Params:
            remote_conn (ConnectionAbstract):
            local_path (str)
                Local path to folder.
            remote_path (str):
                Remote path to folder.
            verbose (bool):
                Log more info.
        """
        self.verbose = verbose

        # pyre-fixme[4]: Attribute must be annotated.
        self.connection = remote_conn
        self.local_path = pathlib.Path(local_path)
        self.remote_path = pathlib.Path(remote_path)

        timestamp = str(int(time.time()))
        self.remote_tarfile = pathlib.Path(
            f"{FolderTransfer.REMOTE_PREFIX}_{timestamp}.tar.gz"
        )
        self.local_tarfile = pathlib.Path(
            f"{FolderTransfer.LOCAL_PREFIX}_{timestamp}.tar.gz"
        )

    def transfer_to_remote(self, create: bool = True, overwrite: bool = True) -> None:
        """
        Put a local folder onto a remote host.

        Params:
            create (bool, optional):
                If true, creates the dest folder if possible.
            overwrite (bool, optional):
                If true, will overwrites the file. True by default.
        Returns:
            None
        """
        AutovalLog.log_info(
            f"Copying {self.local_path} to remote host {self.connection.hostname} at {self.remote_path}"
        )
        try:
            self._check_dir(local=True, create_if_missing=False)  # Check Local Folder
            self._check_dir(
                local=False, create_if_missing=create
            )  # Check Remote Folder
            self._create_tar(local=True)  # Create Local Tar
            self._transfer_tar(to_local=False)  # Transfer Tarfile to remote.
            self._unpack_tar(local=False, overwrite=overwrite)  # Unpack Remote Tar
        finally:
            self._rm_temp_tars()

    def transfer_from_remote(self, create: bool = True, overwrite: bool = True) -> None:
        """
        Get a remote folder onto local.

        Params:
            create (bool, optional):
                If true, creates the dest folder if possible.
            overwrite (bool, optional):
                If true, will overwrites the file. True by default.
        Returns:
            None
        """
        AutovalLog.log_info(
            f"Copying {self.remote_path} from remote host {self.connection.hostname} to {self.local_path}"
        )
        try:
            self._check_dir(local=False, create_if_missing=False)  # Check Remote Folder
            self._check_dir(local=True, create_if_missing=create)  # Check Local Folder
            self._create_tar(local=False)  # Create Remote Tar.
            self._transfer_tar(to_local=True)  # Transfer Tarfile to local.
            self._unpack_tar(local=True, overwrite=overwrite)  # Unpack Local Tar
        finally:
            self._rm_temp_tars()

    # pyre-fixme[2]: Parameter must be annotated.
    def vlog(self, *args, **kwargs) -> None:
        """
        Logs if verbose is set on this object.

        Params:
            Same as AutovalLog.log_info

        Returns:
            None
        """
        if self.verbose:
            AutovalLog.log_info(*args, **kwargs)

    # pyre-fixme[2]: Parameter must be annotated.
    def _check_dir(self, *, local, create_if_missing) -> None:
        """
        Check if a directory exists.

        Params:
            local (bool):
                If True, checks local. Otherwise checks remote.
            create_if_missing (bool):
                If True, will create the folder if missing. Else will return a failed status.
        """
        # Case where we are checking local and create if it is missing.
        if local and create_if_missing:
            try:
                self.vlog(f"Creating folder {self.local_path} on local system.")
                if not self.local_path.is_dir():
                    self.local_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise FolderTransferError(
                    f"Failed to create {self.local_path} on local system. Error: {e}",
                    # pyre-fixme[16]: `fec` has no attribute
                    #  `LOCAL_FOLDER_CREATION_FAILURE`.
                    fec.LOCAL_FOLDER_CREATION_FAILURE,
                )
        # Case where we are checking local and err on missing
        elif local and not create_if_missing:
            if not self.local_path.is_dir():
                raise FolderTransferError(
                    f"Directory {self.local_path} does not exist on local system.",
                    fec.LOCAL_FOLDER_DOES_NOT_EXIST,
                )
        # Case where we are checking remote and create if it is missing.
        elif not local and create_if_missing:
            self.vlog(f"Creating {self.remote_path} on {self.connection.hostname}.")
            mkdir = self.connection.run_get_result(
                f"mkdir -p {self.remote_path}", ignore_status=True
            )
            if mkdir.return_code != 0:
                raise FolderTransferError(
                    f"Could not create {self.remote_path} on {self.connection.hostname}. Error: {mkdir.stdout} {mkdir.stderr}",
                    fec.REMOTE_FOLDER_CREATION_ERROR,
                )
        # Case where we are checking remote and err on missing
        else:
            chk_dir = self.connection.run_get_result(
                f"[ -d {self.remote_path} ]", ignore_status=True
            )
            if chk_dir.return_code != 0:
                raise FolderTransferError(
                    (
                        f"Folder {self.remote_path} missing on {self.connection.hostname}."
                        + f" Error (rc={chk_dir.return_code}): {chk_dir.stdout} {chk_dir.stderr}"
                    ),
                    fec.REMOTE_FOLDER_DOES_NOT_EXIST,
                )

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def _get_folder_and_tar(self, local):
        """
        Get the folder name and the tarfile name given if local or not.

        Params:
            local (bool):
                Returns local folder/tarfile name.
                Otherwise will remote folder/tarfile name
        """
        if local:
            return (self.local_path, self.local_tarfile)
        return (self.remote_path, self.remote_tarfile)

    # pyre-fixme[2]: Parameter must be annotated.
    def _create_tar(self, *, local) -> None:
        """
        Creates a tarfile from the folder.

        Params:
            local (bool):
                Create the local tarfile from the local folder if True.
                Otherwise will create the remote tarfile from the remote folder.
        """

        folder_path, tar_path = self._get_folder_and_tar(local)

        # Tar directory
        tar_cmd = f"tar -C {folder_path} -czf {tar_path} ."

        if local:
            self.vlog(f"Tar-ing local folder {folder_path} to {tar_path}")
            tar_run = AutovalUtils._run_local(tar_cmd, ignore_status=True)
        else:
            self.vlog(
                f"Tar-ing remote {self.connection.hostname} folder {folder_path} to {tar_path}"
            )
            tar_run = self.connection.run_get_result(
                tar_cmd,
                ignore_status=True,
            )

        # If issue with tar-ing -- raise error.
        if tar_run.return_code != 0:
            ec = fec.LOCAL_TAR_ERROR if local else fec.REMOTE_TAR_ERROR
            msg = (
                f"Failed to create local tar file {tar_path} from {folder_path}. "
                if local
                else f"Failed to create remote ({self.connection.hostname}) tar file {tar_path} from {folder_path}. "
            )
            msg += (
                f"Error (rc={tar_run.return_code}): {tar_run.stdout} {tar_run.stderr}"
            )
            raise FolderTransferError(msg, ec)

    # pyre-fixme[2]: Parameter must be annotated.
    def _transfer_tar(self, *, to_local) -> None:
        """
        Transfer tar from local to remote or vice versa.

        Param:
            to_local (bool):
                Transfer from remote to local if True, otherwise from local to remote.
        """

        if to_local:
            try:
                self.vlog(
                    f"Retriving {self.remote_tarfile} on {self.connection.hostname} to {self.local_tarfile}."
                )
                self.connection.get_file(
                    str(self.remote_tarfile), str(self.local_tarfile)
                )
            except Exception as e:
                msg = (
                    f"Failed to retrieve {self.remote_tarfile} on {self.connection.hostname}"
                    + f" to {self.local_tarfile}. Error: {e}"
                )
                raise FolderTransferError(msg, fec.DATA_TRANSFER_ERROR)

        else:
            try:
                self.vlog(
                    f"Putting {self.local_tarfile} to {self.remote_tarfile} on {self.connection.hostname}."
                )
                self.connection.put_file(
                    str(self.local_tarfile), str(self.remote_tarfile)
                )
            except Exception as e:
                msg = (
                    f"Failed to send {self.local_tarfile} to {self.remote_tarfile} on"
                    + f" {self.connection.hostname}. Error: {e}"
                )
                raise FolderTransferError(msg, fec.DATA_TRANSFER_ERROR)

    # pyre-fixme[2]: Parameter must be annotated.
    def _unpack_tar(self, *, local, overwrite) -> None:
        """
        Unpacks a tarfile into a folder.

        Params:
            local (bool):
                Unpacks the local tarfile from the local folder if True.
                Otherwise will unpack the remote tarfile from the remote folder.
        """
        folder_path, tar_path = self._get_folder_and_tar(local)

        # UnTar directory
        ow_str = "--skip-old-files" if not overwrite else "--overwrite"
        tar_cmd = f"tar -xf {tar_path} --directory {folder_path} {ow_str}"

        if local:
            self.vlog(f"Untar-ing local folder {folder_path} to {tar_path}")
            tar_run = AutovalUtils._run_local(tar_cmd, ignore_status=True)
        else:
            self.vlog(
                f"Untar-ing remote {self.connection.hostname} folder {folder_path} to {tar_path}"
            )
            tar_run = self.connection.run_get_result(
                tar_cmd,
                ignore_status=True,
            )

        # If issue with untar-ing -- raise error.
        if tar_run.return_code != 0:
            ec = fec.LOCAL_UNTAR_ERROR if local else fec.REMOTE_UNTAR_ERROR
            msg = (
                f"Failed to untar local tar file {tar_path} from {folder_path}. "
                if local
                else f"Failed to untar remote ({self.connection.hostname}) tar file {tar_path} from {folder_path}. "
            )
            msg += (
                f"Error (rc={tar_run.return_code}): {tar_run.stdout} {tar_run.stderr}"
            )
            raise FolderTransferError(msg, ec)

    def _rm_temp_tars(self) -> None:
        """
        Removes temp tars.
        """
        self.vlog("Removing Temp Tars from Remote and Local.")

        # Remove files
        try:
            self.vlog(f"Removing {self.local_tarfile}.")
            self.local_tarfile.unlink()
        except Exception:
            pass

        self.vlog(
            f"Removing {self.remote_tarfile} on remote host {self.connection.hostname}."
        )
        self.connection.run_get_result(
            f"rm -f {self.remote_tarfile}", ignore_status=True
        )

        # Check removal
        if self.local_tarfile.is_file():
            raise FolderTransferError(
                f"Failed to remove local tar {self.local_tarfile}",
                fec.LOCAL_REMOVAL_ERROR,
            )

        chk_file = self.connection.run_get_result(
            f"[ -f {self.remote_tarfile} ]", ignore_status=True
        )
        if chk_file.return_code == 0:
            raise FolderTransferError(
                f"Failed to remove remote tar {self.remote_tarfile} on host {self.connection.hostname}",
                fec.REMOTE_REMOVAL_ERROR,
            )
