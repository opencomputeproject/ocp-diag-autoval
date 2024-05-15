import concurrent.futures

from autoval.lib.host.component.component import Component
from autoval.lib.utils.autoval_log import AutovalLog


class ComponentBMC(Component):
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
        # pyre-fixme[4]: Attribute must be annotated.
        self.log_dir = logdir

    def check_present(self) -> bool:
        return any(self.host.oobs)

    # pyre-fixme[3]: Return type must be annotated.
    def get_config(self):
        AutovalLog.log_cmdlog("++++Start of BMC component Config Check++++")
        config = {}
        # Concurrent Future ThreadPoolExecutor - Implementation
        # Here we're parallelizing the get config from BMCs(eg: Zion has 4 BMCs)
        with concurrent.futures.ThreadPoolExecutor(max_workers=None) as executor:
            future_list = []
            for oob in filter(None, self.host.oobs):
                future = executor.submit(oob.get_config, self.log_dir, start=self.start)
                future_list.append(future)

            for f in concurrent.futures.as_completed(future_list):
                try:
                    result = f.result()
                    config.update(result)
                except Exception:
                    executor.shutdown(wait=False)
                    raise
        AutovalLog.log_cmdlog("++++End of BMC component Config Check++++")
        return config
