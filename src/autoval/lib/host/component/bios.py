from autoval.lib.host.component.component import Component


class ComponentBIOS(Component):
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
        self.start = start
        # pyre-fixme[4]: Attribute must be annotated.
        self.host = host

    def check_present(self) -> bool:
        return True

    # pyre-fixme[3]: Return type must be annotated.
    def get_config(self):
        return self.host.bios.get_config()
