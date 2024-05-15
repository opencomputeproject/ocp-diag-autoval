from autoval.lib.host.component.component import Component
from autoval.lib.utils.autoval_log import AutovalLog


class ComponentASIC(Component):
    def __init__(
        self,
        # pyre-fixme[2]: Parameter must be annotated.
        host,
        start: bool = True,
        # pyre-fixme[2]: Parameter must be annotated.
        logdir=None,
        # pyre-fixme[2]: Parameter must be annotated.
        start_time=None,
        # pyre-fixme[2]: Parameter must be annotated.
        dump_location=None,
    ) -> None:
        # pyre-fixme[4]: Attribute must be annotated.
        self.host = host
        self.start = start

    def check_present(self) -> bool:
        return True

    # pyre-fixme[3]: Return type must be annotated.
    def get_config(self):
        # pyre-fixme[21]: Could not find module `autoval.lib.host.device.accelerator`.
        from autoval.lib.host.device.accelerator import Accelerator

        AutovalLog.log_cmdlog("++++Start of ASCI Component Config Check++++")
        config = {}
        asic_types = self.host.get_supported_asics()
        for asic_type in asic_types:
            device = self.host._get_device_type(asic_type)
            AutovalLog.log_info("+++Getting ASIC info for {}".format(device))
            config.update(asic_type.get_config())
            # pyre-fixme[16]: Module `host` has no attribute `device`.
            if self.start and isinstance(asic_type, Accelerator):
                asic_type.log_fw_version()
                asic_type.log_driver_version()
        AutovalLog.log_cmdlog("++++End of ASCI Component Config Check++++")
        return config
