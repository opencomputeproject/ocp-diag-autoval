#!/usr/bin/env python3
DEFAULT_LEGACYBMC_USERNAME = "USERID"
DEFAULT_LEGACYBMC_PASSWORD = "PASSW0RD"

DEFAULT_OPENBMC_USERNAME = "root"
DEFAULT_OPENBMC_PASSWORD = "0penBmc"


class Credentials:
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_legacybmc_credentials(self, hostname, username=None, oob_addr=None):
        _username = DEFAULT_LEGACYBMC_USERNAME
        _password = DEFAULT_LEGACYBMC_PASSWORD
        return (_username, _password)

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def get_openbmc_credentials(self, hostname, oob_addr=None, username=None):
        _username = DEFAULT_OPENBMC_USERNAME
        _password = DEFAULT_OPENBMC_PASSWORD
        return (_username, _password)
