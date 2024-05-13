import concurrent.futures

from autoval.lib.host.component.component import Component
from autoval.lib.utils.autoval_log import AutovalLog


class ComponentBMC(Component):
    def __init__(
        self, host, start: bool = True, logdir=None, start_time=None, dump_location=None
    ) -> None:
        self.start = start
        self.host = host
        self.log_dir = logdir

    def check_present(self) -> bool:
        return any(self.host.oobs)

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
