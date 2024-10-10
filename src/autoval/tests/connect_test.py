#!/usr/bin/env python3

# pyre-unsafe

from autoval.lib.host.component.component import COMPONENT
from autoval.lib.test_base import TestBase
from autoval.lib.utils.autoval_errors import ErrorType


class ConnectTest(TestBase):
    """
    Connects to DUT and BMC and runs Config Check.
    Verifies that system is accessible.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    # pyre-fixme[14]: `setup` overrides method defined in `TestBase` inconsistently.
    def setup(self) -> None:
        super(ConnectTest, self).setup()

    def execute(self) -> None:
        validation_failures = []
        host = self.host

        self.validate_no_exception(
            host.run,
            ["hostname"],
            "connected to host",
            component=COMPONENT.SYSTEM,
            error_type=ErrorType.NOT_ACCESSIBLE_ERR,
        )
        
        oob = host.oob
        if oob and oob.oob_addr:
            self.validate_no_exception(
                host.ping_bmc,
                [],
                "ping %s" % (oob.oob_addr),
                component=COMPONENT.BMC,
                error_type=ErrorType.NOT_ACCESSIBLE_ERR,
            )
        else:
            self.log_info("{} with no BMC".format(host.hostname))


    # pyre-fixme[14]: `cleanup` overrides method defined in `TestBase` inconsistently.
    def cleanup(self) -> None:
        super(ConnectTest, self).cleanup()
