#!/usr/bin/env python3

# pyre-unsafe

import os
from typing import Dict, List

from autoval.lib.host.host import Host
from autoval.lib.test_args import TEST_HOSTS
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.file_actions import FileActions
from autoval.lib.utils.site_utils import SiteUtils

golden_config_table_keys = {"asset": {"os": "os_version", "kernel": "kernel"}}
golden_config_component_table = {"DUT": {"component": "asset", "id": "asset_id"}}


class GoldenConfigCheck:
    def golden_config_check(self, host: "Host", config_dict: Dict):
        """
        Reads the golden_config.json file.
        Compares the data with the config_dict

        To map the keys it makes use of the dict golden_config_table_keys

        format of golden_config.json goes as below,

        {
        part_number1: [{asset: {}, cpu:[{}, {}, {}]}
                       {asset: {}, cpu:[{}, {}, {}]}
                      ]

        part_number2: [{asset: {}, cpu:[{}]}]


        }

        The above dict refers its a multi host system where two of the
        hosts belong to Model-A (eg. BryceCanyon) and have three cpus each.
        And one of them belongs to model-B has one cpu.


        Config dictionary has the below format

        {
        'DUT': {"id1": {}, "id2": {}}
        'CPU': {"id1": {}}
        }
        @return : It will return {} when golden config check succeeds.
                  On failures, it will return a diff as below
                  {'asset':
                    {'<asset_id>':
                        {'kernel': ['4.16.18-202', '4.16.18-202_mod']
                        }
                    }
                }

        """
        golden_config_table = self.get_golden_config(host)

        diff = {}
        for asset_list in golden_config_table.values():
            for host_data in asset_list:
                for component, component_dict in host_data.items():
                    diff.update(
                        self.compare_component_dict(
                            config_dict, component, component_dict
                        )
                    )
        return diff

    def compare_component_dict(
        self, config_dict, golden_config_component, golden_config_component_dict
    ):
        """
        This functions compares all the components that belong to a single asset.

        It first compares the system data (asset/DUT specific data),

        then iterates over the list of every hardware component.

        """
        diff = {}
        for config_component, config_component_dict in config_dict.items():
            if config_component == "DUT" and golden_config_component == "asset":
                diff_asset = self.compare_dict(
                    golden_config_component_dict,
                    config_component_dict,
                    golden_config_component="asset",
                )
                if diff_asset:
                    asset_id = golden_config_component_dict.get(
                        "asset_id", "golden_config_missing_asset_id"
                    )
                    diff.update({"asset": {str(asset_id): diff_asset}})
            elif config_component == golden_config_component.upper() or (
                config_component in golden_config_component_table
                and golden_config_component_table[config_component]["component"]
                == golden_config_component
            ):
                """
                list of hardware data (of an asset) are stored in
                golden_config_component_dict

                Eg1:
                    cpu:
                        [
                            {cpu1 data},
                            {cpu2 data}
                        ],

                    disk:
                        [
                            {disk1 data},
                            {disk2 data}
                        ]


                """
                for golden_config_hardware_dict in golden_config_component_dict:

                    diff_hardware = self.compare_dict(
                        golden_config_hardware_dict,
                        config_component_dict,
                        golden_config_component=golden_config_component,
                    )
                    if diff_hardware:
                        hw_component_id = golden_config_hardware_dict.get(
                            golden_config_component_table[config_component]["id"],
                            "golden_config_missing_hw_id",
                        )
                        diff.update(
                            {
                                golden_config_component: {
                                    str(hw_component_id): diff_hardware
                                }
                            }
                        )
        return diff

    def compare_dict(
        self, golden_config_dict, component_dict, golden_config_component=None
    ):
        diff = {}
        for config_data in component_dict.values():
            diff.update(
                self.is_match(
                    golden_config_dict,
                    config_data,
                    golden_config_component=golden_config_component,
                )
            )
            if diff:
                break
        return diff

    def is_match(
        self, golden_config_component_dict, config_data, golden_config_component=None
    ):
        config_key = ""
        key = ""
        for key, value in golden_config_component_dict.items():
            if (
                golden_config_component in golden_config_table_keys
                and key in golden_config_table_keys[golden_config_component]
            ):
                config_key = golden_config_table_keys[golden_config_component][key]
                if (
                    key in golden_config_table_keys[golden_config_component]
                    and config_key in config_data
                ):
                    if value == config_data[config_key]:
                        continue
                    else:
                        return {str(key): [value, config_data[config_key]]}
            else:
                continue
        return {}

    def get_golden_config(self, host: "Host"):
        """
        Get golden config based on the availability in the following locations
        1. system_logs in result directory
        2. Gluster Share/golden_config/<golden_config_<part_number>.json
        3.  Gluster Share/golden_config/<platform>.json
        @param Host host : Host Object
        @return Dict : json contents of goldern config
        """
        golden_config = os.path.join(
            SiteUtils().get_system_logdir(), "golden_config.json"
        )
        if FileActions.exists(golden_config):
            return FileActions.read_data(golden_config, json_file=True)

        # golden_config File will not be generated for Hi5 test,
        # Pulling this from the given part_number
        part_number = self.get_part_number_from_test_config(host.hostname)
        golden_config_file = "golden_config_" + part_number + ".json"
        golden_config = os.path.join(
            SiteUtils().get_golden_config_path(), golden_config_file
        )
        if FileActions.exists(golden_config):
            return FileActions.read_data(golden_config, json_file=True)

        # Pulling from Platform specific config file
        product = host.get_sanitized_product_name()
        golden_config = os.path.join(
            SiteUtils().get_golden_config_path(), product + ".json"
        )

        if FileActions.exists(golden_config):
            return FileActions.read_data(golden_config, json_file=True)
        # TODO Raise Exception, Once GoldenConfig is stable
        AutovalLog.log_info(
            "Unable to get the GoldenConfig File from %s"
            % SiteUtils().get_golden_config_path()
        )
        return {}

    def get_boot_drive_from_golden_config(self, host: "Host") -> List:
        golden_config_data = self.get_golden_config(host)
        # Get Boot drive location if the fbpn and BOM file is available
        drive_locations = []
        for _fbpn, systems in golden_config_data.items():
            for system in systems:
                for drive in system["Disk"]:
                    if drive["is_bootdrive"] is True:
                        drive_locations.append(drive["location"])
        return drive_locations

    def get_nics_from_golden_config(self, host: "Host") -> Dict:
        nic_devices = {}
        no_of_nic_devices = 0
        golden_config_data = self.get_golden_config(host)
        for asset_list in golden_config_data.values():
            for host_data in asset_list:
                is_nic_available = False
                for component, component_dict in host_data.items():
                    if "NetworkInterfaceCard" in component:
                        is_nic_available = True
                        no_of_nic_devices = len(component_dict)
                        nic_devices[host_data["asset"]["name"]] = no_of_nic_devices
                if not is_nic_available:
                    nic_devices[host_data["asset"]["name"]] = 0
        return nic_devices

    def get_part_number_from_test_config(self, hostname: str) -> str:
        part_number = ""
        for host in TEST_HOSTS:
            if host["hostname"] == hostname:
                part_number = host.get("part_number", "")
                break
        return part_number
