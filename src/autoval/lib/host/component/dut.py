from autoval.lib.host.component.component import Component

# pyre-fixme[21]: Could not find module `autoval.lib.test_utils.pci_utils`.
from autoval.lib.test_utils.pci_utils import PciUtils

# pyre-fixme[21]: Could not find module `autoval.lib.test_utils.system_utils`.
from autoval.lib.test_utils.system_utils import get_acpi_interrupt, get_serial_number

from autoval.lib.utils.autoval_log import AutovalLog


class ComponentDUT(Component):
    def __init__(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        host,
        start: bool = True,
        # pyre-fixme[2]: Parameter must be annotated.
        logdir=None,
        # pyre-fixme[2]: Parameter must be annotated.
        start_time=None,
        # pyre-fixme[2]: Parameter must be annotated.
        dump_location=None,
    ) -> None:
        self.start = start
        # pyre-fixme[4]: Attribute must be annotated.
        self.host = host
        # pyre-fixme[4]: Attribute must be annotated.
        self.dump_location = dump_location
        # pyre-fixme[4]: Attribute must be annotated.
        self.log_dir = logdir
        # pyre-fixme[4]: Attribute must be annotated.
        self.start_time = start_time

    def check_present(self) -> bool:
        return True

    # pyre-fixme[3]: Return type must be annotated.
    def get_config(self):
        AutovalLog.log_cmdlog("++++Start of DUT Component Config Check++++")
        AutovalLog.log_debug("+++Getting DUT info")
        dut_info = {}
        dut_info["fru_board_mfg"] = ""
        dut_info["fru_board_product"] = ""
        dut_info["bmc_type"] = self.host.bmc_type
        AutovalLog.log_debug("+++BMC type is: %s" % (dut_info["bmc_type"]))
        AutovalLog.log_debug("+++Getting general info")
        dut_info.update(self.host.get_generalinfo())
        AutovalLog.log_debug("+++Getting lsscsi info")
        dut_info.update(self.host.get_lsscsi_info(self.host))
        AutovalLog.log_debug("+++Getting mem info")
        dut_info.update(self.host.get_meminfo())
        AutovalLog.log_debug("+++Getting lspci info")
        # pyre-fixme[16]: Module `test_utils` has no attribute `pci_utils`.
        dut_info["lspci"] = PciUtils().get_lspci_output(self.host)
        AutovalLog.log_debug("+++Getting project info")
        dut_info.update(self.host.get_project_info())

        AutovalLog.log_debug("+++Getting BIC version")
        bic_dict = self.host.get_bic_fw_version()
        if bic_dict is None:
            AutovalLog.log_debug(
                "DUT does not support obtaining BIC version via ipmitool. Skipping BIC FW Version."
            )
        else:
            dut_info.update(bic_dict)

        AutovalLog.log_debug("+++Getting lspci verbose info")
        # pyre-fixme[16]: Module `test_utils` has no attribute `pci_utils`.
        dut_info.update(PciUtils().get_lspci_verbose(self.host, self.start))

        AutovalLog.log_debug("+++Getting system log errors")
        dut_info.update(
            self.host.get_syslogs(self.start, self.dump_location, self.start_time)
        )

        if self.host.is_root:
            # pyre-fixme[16]: Module `test_utils` has no attribute `system_utils`.
            serial_number = get_serial_number("baseboard", self.host)
        else:
            serial_number = "UNKNOWN"
        # pyre-fixme[16]: Module `test_utils` has no attribute `system_utils`.
        dut_info["acpi_difference"] = get_acpi_interrupt(self.host)
        dut_info.update(self.host.get_config())
        AutovalLog.log_cmdlog("++++End of DUT Component Config Check++++")
        return {serial_number: dut_info}
