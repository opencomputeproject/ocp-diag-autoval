from autoval.lib.host.component.component import Component


class ComponentCPU(Component):
    def __init__(
        self, host, start: bool = True, logdir=None, start_time=None, dump_location=None
    ) -> None:
        self.start = start
        self.host = host

    def check_present(self) -> bool:
        return True

    def get_config(self):
        return self.host.cpuinfo.get_config()
