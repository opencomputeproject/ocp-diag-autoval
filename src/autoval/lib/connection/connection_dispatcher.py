#!/usr/bin/env python3
import re

from autoval.lib.connection.connection_factory import ConnectionFactory
from autoval.lib.host.credentials import Credentials


class ConnectionDispatcher:
    def __init__(self, host, skip_health_check: bool = False) -> None:
        self.host_dict = host
        self.skip_health_check = skip_health_check
        self.hostname = self.host_dict.get("hostname", None)
        self._oob_addr = ""
        self._host_port = None
        self.oob_only = True if not self.hostname else False
        self._host_connection = None
        self._bmc_connections = []
        self._localhost = None
        self.rack_sub_position_slot = host.get("rack_sub_position_slot", None)

    @property
    def oob_addr(self):
        if self.bmc_connections[0] and not self._oob_addr:
            self._oob_addr = self.bmc_connections[0].hostname
        return self._oob_addr

    @property
    def host_port(self):
        return self._host_port

    @property
    def host_connection(self):
        if not self._host_connection:
            password = self.host_dict.get("password", None)
            self._host_connection = ConnectionFactory.create(
                hostname=self.hostname,
                user=self.host_dict.get("username", None),
                password=password,
                skip_health_check=self.skip_health_check,
                force_thrift=self.host_dict.get("force_thrift", False),
                force_ssh=self.host_dict.get("force_ssh", False),
                local_mode=self.host_dict.get("local_mode", False),
                sudo=self.host_dict.get("sudo", False),
                port=self.host_port,
            )
        return self._host_connection

    @property
    def bmc_connections(self):
        if not self._bmc_connections:
            self._bmc_connections.extend(self._get_oob_connections())
        return self._bmc_connections

    def _get_oob_connections(self):
        """Constructing additional BMCs connection objects"""
        bmc_connections = []
        oob_addr_keys = [
            key for key in self.host_dict.keys() if re.search(r"oob\d*_addr", key)
        ]
        if "oob_addr" not in oob_addr_keys:
            bmc_connections.append(None)
        for oob_addr_key in oob_addr_keys:
            oob_addr = self.host_dict.get(oob_addr_key)
            match = re.search(r"oob(\d)_addr", oob_addr_key)
            oob_index = match.group(1) if match else ""
            oob_password = self.host_dict.get(f"oob{oob_index}_password", None)
            oob_username = self.host_dict.get(f"oob{oob_index}_username", None)
            if not oob_username or not oob_password:
                oob_username, oob_password = Credentials.get_openbmc_credentials(
                    self.hostname, oob_addr
                )
            bmc_connections.append(
                ConnectionFactory.create(
                    oob_addr,
                    force_ssh=True,
                    user=oob_username,
                    password=oob_password,
                    allow_agent=False,
                )
            )
        return bmc_connections

    @property
    def localhost(self):
        if not self._localhost:
            self._localhost = ConnectionFactory.create("localhost", local_mode=True)
        return self._localhost
