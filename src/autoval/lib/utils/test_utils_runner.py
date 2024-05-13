#!/usr/bin/env python3
from typing import Any

from autoval.lib.host.host import Host
from autoval.lib.utils.autoval_utils import AutovalUtils
from autoval.lib.utils.site_utils import SiteUtils
from autoval.lib.utils.test_utils_base import TestUtilsBase
from autoval.plugins.plugin_manager import PluginManager


# traceback.print_stack()

"""
Supported TestUtilsBase extended tests
"""


class TestUtilsRunner(TestUtilsBase):
    """
    Utility to run the test which extended TestUtilsBase
    """

    def __init__(self, host, util: str, util_args) -> None:
        super(TestUtilsRunner, self).__init__()
        self.host = Host(AutovalUtils.get_host_dict(host))
        self.util_obj = None
        self.initialize_util(util, util_args)

    def initialize_util(self, util: str, util_args) -> None:
        test_utils_config_path = SiteUtils.get_test_utils_plugin_config_path()
        PluginManager.load_plugins(test_utils_config_path)
        if util in PluginManager._plugin_map.keys():
            self.util_obj = PluginManager.get_plugin_cls(util)(self.host, util_args)

    def test_setup(self) -> None:
        self.util_obj.test_setup()

    def test_cleanup(self) -> None:
        self.util_obj.test_cleanup()

    def start_test(self) -> None:
        self.util_obj.start_test()

    def stop_test(self, *args, **kwargs) -> None:
        if "stop_test" in dir(self.util_obj):
            self.util_obj.stop_test(*args, **kwargs)

    def parse_results(self) -> Any:
        self.util_obj.parse_results()
