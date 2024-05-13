#!/usr/bin/env python3

from typing import Dict

from autoval.lib.host.component.asic import ComponentASIC
from autoval.lib.host.component.bios import ComponentBIOS
from autoval.lib.host.component.bmc import ComponentBMC
from autoval.lib.host.component.cpu import ComponentCPU
from autoval.lib.host.component.dut import ComponentDUT
from autoval.lib.host.component.nic import ComponentNIC
from autoval.lib.test_args import TEST_CONTROL
from autoval.lib.utils.autoval_log import AutovalLog


class ComponentFactory:
    def __init__(self, host) -> None:
        self.host = host
        self.config_components = TEST_CONTROL.get("config_components", None)
        self._supported_components: Dict = {
            "DUT": ComponentDUT,
            "BMC": ComponentBMC,
            "CPU": ComponentCPU,
            "NIC": ComponentNIC,
            "BIOS": ComponentBIOS,
            "ASIC": ComponentASIC,
        }

    def create(self, start_time=None):
        AutovalLog.log_debug("Started preparing the attached component list")
        components = []
        for _comp in self._supported_components:
            comp_obj = self._supported_components[_comp]
            if comp_obj:
                if not self.config_components or _comp in self.config_components:
                    if comp_obj(self.host, start_time=start_time).check_present():
                        AutovalLog.log_debug(
                            f"{_comp} is present. Adding it to components list"
                        )
                        components.append((_comp, comp_obj))

        return components
