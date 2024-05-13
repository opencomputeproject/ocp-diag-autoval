from autoval.lib.host.component.component import Component
from autoval.lib.utils.autoval_log import AutovalLog


class ComponentASIC(Component):
    def __init__(
        self, host, start: bool = True, logdir=None, start_time=None, dump_location=None
    ) -> None:
        self.host = host
        self.start = start

    def check_present(self) -> bool:
        return True

    def get_config(self):
        from autoval.lib.host.device.accelerator import Accelerator

        AutovalLog.log_cmdlog("++++Start of ASCI Component Config Check++++")
        config = {}
        asic_types = self.host.get_supported_asics()
        for asic_type in asic_types:
            device = self.host._get_device_type(asic_type)
            AutovalLog.log_info("+++Getting ASIC info for {}".format(device))
            config.update(asic_type.get_config())
            if self.start and isinstance(asic_type, Accelerator):
                asic_type.log_fw_version()
                asic_type.log_driver_version()
        AutovalLog.log_cmdlog("++++End of ASCI Component Config Check++++")
        return config
