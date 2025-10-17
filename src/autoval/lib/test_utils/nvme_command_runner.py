#!/usr/bin/env python3

# pyre-unsafe
import os
from typing import Any

from autoval.lib.test_args import TEST_CONTROL

# pyre-fixme[21]: Could not find module `autoval.lib.test_utils.test_utils_base`.
from autoval.lib.test_utils.test_utils_base import TestUtilsBase

from autoval.lib.utils.async_utils import AsyncJob, AsyncUtils
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.site_utils import SiteUtils

from autoval_ssd.lib.utils.pci_utils import PciUtils

from autoval_ssd.lib.utils.storage.nvme.nvme_drive import NVMeDrive

from autoval_ssd.lib.utils.storage.storage_utils import StorageUtils


# pyre-fixme[11]: Annotation `TestUtilsBase` is not defined as a type.
class NvmeCommandRunner(TestUtilsBase):
    """
    This is used for running the commands on the drives in parallel FIO job
    nvme_commands executed only on NVME drives
    smart_commands executed on ALL drives
    all_commands is combined mode from nvme_commands and smart_commands
    """

    def __init__(self, host, args) -> None:
        super(NvmeCommandRunner).__init__()
        self.host = host
        self.args = args
        self.commands = args.get("commands", "all_commands")
        self.default_state = {}
        self.enable_async_log_storing = args.get("enable_async_log_storing", True)

    def test_setup(self) -> None:
        """
        This will get the list of all drives on the DUT.
        """
        # pyre-fixme[16]: `NvmeCommandRunner` has no attribute `drives`.
        self.drives = self.args.get("drives", [])
        if len(self.drives) == 0:
            drive_list = StorageUtils.get_test_drives(self.host)
            self.drives = drive_list.values()
        logdirs = SiteUtils().get_log_dirs()
        resultdir = logdirs["resultsdir"]
        # pyre-fixme[16]: `NvmeCommandRunner` has no attribute `smart_log_dir`.
        self.smart_log_dir = os.path.join(resultdir, "SMART")

    def start_test(self) -> None:
        if "nvme_commands" in self.commands:
            # Only NVME commands for SSD drives
            AsyncUtils.run_async_jobs(
                [
                    AsyncJob(func=self.run_nvme_commands, args=[drive])
                    # pyre-fixme[16]: `NvmeCommandRunner` has no attribute `drives`.
                    for drive in self.drives
                    if drive.interface.value == "nvme"
                ]
            )
        elif "smart_commands" in self.commands:
            # Only SMART commands for all drives
            self.run_get_smart_data()
        else:
            # Run NVME commands on SSD drives and SMART commands on all drives
            self.run_get_smart_data()
            AsyncUtils.run_async_jobs(
                [
                    AsyncJob(func=self.run_nvme_commands, args=[drive])
                    for drive in self.drives
                    if drive.interface.value == "nvme"
                ]
            )

    def run_nvme_commands(self, drive: NVMeDrive) -> None:
        """
        This method is used to run the various nvme commands

        Parameters
        ---------
        drive : :obj: 'Drive'
            The drive's name present in the host for the specific drive type.
        """
        telemetry_log = TEST_CONTROL.get("collect_telemetry_log", False)
        if telemetry_log:
            AutovalLog.log_info("Collecting telemetry log")
            drive.get_internal_log(timeout=1200, flag=" -d 1")
        else:
            AutovalLog.log_info("Collecting smart log")
            drive.get_fw_log()
            drive.get_smart_log()
            drive.get_error_log()
            self.cto_disable_check()

    def cto_disable_check(self) -> None:
        """
        Enable and disable the Completion Time Out on NVME drives
        """
        AutovalLog.log_info("Completion TimeOut Disable check")
        default_state = {}
        # pyre-fixme[16]: `NvmeCommandRunner` has no attribute `drives`.
        for drive in self.drives:
            if drive.interface.value == "nvme":
                default_state[
                    drive.block_name
                ] = PciUtils().get_nvme_drive_pcie_completion_timeout_value(
                    self.host, drive.block_name
                )
        for block_name, state in default_state.items():
            if state == "0400":
                PciUtils().set_nvme_drive_pcie_completion_timeout(
                    self.host, block_name, "0410"
                )
                AutovalLog.log_info(
                    "Completion Time out Enabled on drive %s" % block_name
                )
            else:
                PciUtils().set_nvme_drive_pcie_completion_timeout(
                    self.host, block_name, "0400"
                )
                AutovalLog.log_info(
                    "Completion Time out Disabled on drive %s" % block_name
                )

    def run_get_smart_data(self) -> None:
        """
        This method will call the function where the
        drive smart commands are run in parallel and its data collected.
        """
        if self.enable_async_log_storing:
            StorageUtils.save_drive_logs_async(
                self.host,
                # pyre-fixme[16]: `NvmeCommandRunner` has no attribute `drives`.
                self.drives,
                self.smart_log_dir,  # pyre-fixme[16]
            )
        else:
            AsyncUtils.run_async_jobs(
                [AsyncJob(func=drive.collect_data) for drive in self.drives]
            )

    def parse_results(self) -> Any:
        # TODO later after knowing what data to be parse is required.
        pass
