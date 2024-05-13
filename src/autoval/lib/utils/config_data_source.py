from abc import ABC, abstractmethod


class ConfigDataSource(ABC):
    @abstractmethod
    def read_config_as_string(self):
        pass

    @abstractmethod
    def read_config_as_json(self):
        pass
