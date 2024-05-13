#!/usr/bin/env python3

import json

from autoval.lib.utils.config_data_source import ConfigDataSource
from autoval.lib.utils.file_actions import FileActions

"""
Place holder for Hi5 Plugin
"""


class FileSystemConfigDataSource(ConfigDataSource):
    def read_config_as_string(self, filepath: str):
        """
        Reads packaged config from configerator
        filepath is the config path in configerator,
        e.g, havoc/autoval/threshold/fio_runner.json
        havoc/autoval/model_id_type_map/model_id_type_map.json
        """
        _filepath = "/".join(filepath.split("/")[-2:]) + ".json"
        threshold_data = FileActions.read_resource_file(
            file_path=f"cfg/{_filepath}",
        )
        return json.dumps(threshold_data)

    def read_config_as_json(self, filepath: str):
        """
        Reads packaged config from configerator
        filepath is the config path in configerator,
        e.g, havoc/autoval/threshold/fio_runner.json
        havoc/autoval/model_id_type_map/model_id_type_map.json
        """
        _filepath = "/".join(filepath.split("/")[-2:]) + ".json"
        threshold_data = FileActions.read_resource_file(
            file_path=f"cfg/{_filepath}",
        )
        return threshold_data
