import enum
from abc import abstractmethod


class COMPONENT(enum.Enum):
    BIOS = "BIOS"
    NIC = "NIC"
    SSD = "SSD"
    BIC = "BIC"
    ASIC = "ASIC"
    ASIC_MODULE = "ASIC_MODULE"
    CPU = "CPU"
    SYSTEM = "SYSTEM"
    BMC = "BMC"
    GPU = "GPU"
    DIMM = "DIMM"
    TEST = "TEST"
    STORAGE_DRIVE = "STORAGE_DRIVE"
    FAN = "FAN"
    PCI = "PCI"
    PCIE_SWITCH = "PCIE_SWITCH"
    SENSOR = "SENSOR"
    HMC = "HMC"
    HGX = "HGX"
    UNKNOWN = "UNKNOWN"
    NVSWITCH = "NVSWITCH"
    NVLINK = "NVLINK"
    HDD = "HDD"


class Component:
    """
    This will become the superclass for all types of components.

    To add a new component, create a new component class, define the required functions as
    mentioned below and add the component in the component factory under the list of
    supported components.

    get_config() is an abstract method and it must be implemented by every
    component class.

    check_present() needs to be implemented by the individual components to determine
    whether the particular component is present on the DUT.

    """

    # pyre-fixme[2]: Parameter must be annotated.
    def __init__(self, host) -> None:
        # pyre-fixme[4]: Attribute must be annotated.
        self.host = host

    def check_present(self) -> bool:
        return True

    @abstractmethod
    # pyre-fixme[3]: Return type must be annotated.
    def get_config(self):
        return {}
