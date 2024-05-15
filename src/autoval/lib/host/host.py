# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
from typing import Any, Dict, List

from autoval.lib.connection.connection_dispatcher import ConnectionDispatcher
from autoval.lib.host.system import System
from autoval.lib.test_args import TEST_HOSTS
from autoval.lib.utils.decorators import retry


class Host:
    # pyre-fixme[2]: Parameter annotation cannot contain `Any`.
    def __init__(self, host_info: Dict[Any, Any]) -> None:
        # pyre-fixme[4]: Attribute must be annotated.
        self.hostname = host_info["hostname"]
        self.connection_obj = ConnectionDispatcher(host_info)
        # pyre-fixme[4]: Attribute must be annotated.
        self.localhost = self.connection_obj.localhost
        self.system = System(self)
        # pyre-fixme[4]: Attribute must be annotated.
        self.oob = self.system.oob
        # pyre-fixme[4]: Attribute must be annotated.
        self.oob_addr = self.connection_obj.oob_addr
        # pyre-fixme[4]: Attribute annotation cannot contain `Any`.
        self.host_dict = host_info

    # pyre-fixme[3]: Return type must be annotated.
    def __getattr__(self, name: str):
        return getattr(self.system, name)

    @classmethod
    # pyre-fixme[24]: Generic type `list` expects 1 type parameter, use
    #  `typing.List[<element type>]` to avoid runtime subscripting errors.
    def get_hosts_objs(cls, skip_health_check: bool = False) -> List:
        hosts = []
        for _h in TEST_HOSTS:
            hosts.append(Host(_h))
        return hosts

    @retry(tries=6, sleep_seconds=10)
    # pyre-fixme[3]: Return type must be annotated.
    def ping(self):
        try:
            out = self.localhost.run("ping6 -c 3 -i 0.2 %s" % self.hostname)
        except Exception:
            out = self.localhost.run("ping -c 3 -i 0.2 %s" % self.hostname)
        return out

    @retry(tries=6, sleep_seconds=10)
    # pyre-fixme[3]: Return type must be annotated.
    def ping_bmc(self):
        try:
            out = self.localhost.run("ping6 -c 3 -i 0.2 %s" % self.oob_addr)
        except Exception:
            out = self.localhost.run("ping -c 3 -i 0.2 %s" % self.oob_addr)
        return out
