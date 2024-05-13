from autoval.lib.host.component.component import Component
from autoval.lib.test_utils.pci_utils import PciUtils
from autoval.lib.test_utils.system_utils import get_acpi_interrupt, get_serial_number

from autoval.lib.utils.autoval_log import AutovalLog


class ComponentDUT(Component):
    def __init__(
        self, host, start: bool = True, logdir=None, start_time=None, dump_location=None
    ) -> None:
        self.start = start
        self.host = host
        self.dump_location = dump_location
        self.log_dir = logdir
        self.start_time = start_time

    def check_present(self) -> bool:
        return True

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
        dut_info.update(PciUtils().get_lspci_verbose(self.host, self.start))

        AutovalLog.log_debug("+++Getting system log errors")
        dut_info.update(
            self.host.get_syslogs(self.start, self.dump_location, self.start_time)
        )

        if self.host.is_root:
            serial_number = get_serial_number("baseboard", self.host)
        else:
            serial_number = "UNKNOWN"
        dut_info["acpi_difference"] = get_acpi_interrupt(self.host)
        dut_info.update(self.host.get_config())
        AutovalLog.log_cmdlog("++++End of DUT Component Config Check++++")
        return {serial_number: dut_info}
