from abc import ABC, abstractmethod


class ConfigDataSource(ABC):
    @abstractmethod
    # pyre-fixme[3]: Return type must be annotated.
    def read_config_as_string(self):
        pass

    @abstractmethod
    # pyre-fixme[3]: Return type must be annotated.
    def read_config_as_json(self):
        pass
