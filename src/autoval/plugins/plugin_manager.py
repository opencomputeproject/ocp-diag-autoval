#!/usr/bin/env python3
"""
Plugin manager serves plugins on request, it can serve
both plugin 'class objects' (for static/ class attribute access) and
new objects of plugin classes (for instance attribute access)
"""
import json
import os
from importlib import import_module
from typing import Dict

import pkg_resources
from autoval.lib.utils.autoval_exceptions import AutovalFileNotFound

from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.site_utils import SiteUtils


class PluginManager:
    """class for Plugin manager"""

    # pyre-fixme[4]: Attribute must be annotated.
    PLUGIN_CONFIG_PATH = SiteUtils.get_plugin_config_path()
    # _plugin_map is populated on the first call to get_plugin_cls
    # pyre-fixme[4]: Attribute must be annotated.
    _plugin_map = {}

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_plugin_cls(plugin_name):
        """Get a class reference for the requested plugin"""
        if not PluginManager._plugin_map.get(plugin_name, None):
            PluginManager.load_plugins(plugin_name=plugin_name)
        return PluginManager._plugin_map.get(plugin_name)

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def load_class(module: str, class_str):
        """Import specified plugin module"""
        try:
            return getattr(
                import_module(module),
                class_str,
            )
        except Exception as ex:
            raise ex

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def load_plugins(cls, plugin_config_path=None, plugin_name=None) -> None:
        """
        Load plugins from plugin config json file and updates the plugins to plugin dictionary

        Args:
            plugin_config_path : Plugin config file path
            plugin_name : Name of single plugin to be loaded

        Returns:
            None

        Raises:
            Exception if failed to load plugin module
            KeyError if failed to detect the plugin name

        """
        if plugin_config_path is None:
            plugin_config_path = cls.PLUGIN_CONFIG_PATH
        # Read the config file
        AutovalLog.log_debug(f"plugin config path {plugin_config_path}")
        plugins = cls._read_resource_file(file_path=plugin_config_path)
        AutovalLog.log_debug(f"Plugins detected: {plugins}")
        for plugin in plugins:
            # if plugin_name is not given then load all plugins
            if plugin_name is None or plugin["name"] == plugin_name:
                try:
                    plugin_class = cls.load_class(plugin["module"], plugin["class"])
                    AutovalLog.log_debug(f"Plugin {plugin_class} loaded")
                    cls._plugin_map[plugin["name"]] = plugin_class
                    if plugin_name:
                        return
                except BaseException as ex:
                    AutovalLog.log_info(f"Failed to load plugin: {plugin} {ex}")
                    raise ex
        if plugin_name:
            AutovalLog.log_debug(f"Plugin {plugin_name} not found")

    @classmethod
    # pyre-fixme[24]: Generic type `dict` expects 2 type parameters, use
    #  `typing.Dict[<key type>, <value type>]` to avoid runtime subscripting errors.
    def _read_resource_file(cls, file_path: str, module: str = "autoval") -> Dict:
        absolute_file_path = pkg_resources.resource_filename(module, file_path)
        if os.path.exists(absolute_file_path):
            with open(absolute_file_path) as cfg_file:
                return json.load(cfg_file)
        else:
            raise AutovalFileNotFound(
                f"Config file {absolute_file_path} does not exist"
            )
