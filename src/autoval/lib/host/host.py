# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
from typing import Any, Dict, List

from autoval.lib.connection.connection_dispatcher import ConnectionDispatcher
from autoval.lib.host.system import System
from autoval.lib.test_args import TEST_HOSTS
from autoval.lib.utils.decorators import retry


class Host:
    def __init__(self, host_info: Dict[Any, Any]) -> None:
        self.hostname = host_info["hostname"]
        self.connection_obj = ConnectionDispatcher(host_info)
        self.localhost = self.connection_obj.localhost
        self.system = System(self)
        self.oob = self.system.oob
        self.oob_addr = self.connection_obj.oob_addr
        self.host_dict = host_info

    def __getattr__(self, name: str):
        return getattr(self.system, name)

    @classmethod
    def get_hosts_objs(cls, skip_health_check: bool = False) -> List:
        hosts = []
        for _h in TEST_HOSTS:
            hosts.append(Host(_h))
        return hosts

    @retry(tries=6, sleep_seconds=10)
    def ping(self):
        try:
            out = self.localhost.run("ping6 -c 3 -i 0.2 %s" % self.hostname)
        except Exception:
            out = self.localhost.run("ping -c 3 -i 0.2 %s" % self.hostname)
        return out

    @retry(tries=6, sleep_seconds=10)
    def ping_bmc(self):
        try:
            out = self.localhost.run("ping6 -c 3 -i 0.2 %s" % self.oob_addr)
        except Exception:
            out = self.localhost.run("ping -c 3 -i 0.2 %s" % self.oob_addr)
        return out
