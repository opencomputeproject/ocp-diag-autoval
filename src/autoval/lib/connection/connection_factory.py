#!/usr/bin/env python3

import argparse

from autoval.lib.transport.local import LocalConn
from autoval.lib.transport.ssh import SSHConn
from autoval.plugins.plugin_manager import PluginManager


class ConnectionFactory:
    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def _parse_connection_arg(cls):
        parser = argparse.ArgumentParser(description="connection arg")
        parser.add_argument(
            "--thrift",
            "-t",
            default=False,
            action="store_true",
            dest="thrift",
            help="Thrift connection (Default: SSH)",
        )
        args = parser.parse_known_args()[0]
        return args.thrift

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def create(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        hostname,
        force_ssh: bool = False,
        skip_health_check: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        user=None,
        # pyre-fixme[2]: Parameter must be annotated.
        password=None,
        allow_agent: bool = True,
        force_thrift: bool = False,
        local_mode: bool = False,
        sudo: bool = False,
        # pyre-fixme[2]: Parameter must be annotated.
        port=None,
    ):
        if force_thrift:
            # pyre-fixme[16]: `Type` has no attribute `thrift`.
            cls.thrift = True
        elif force_ssh:
            cls.thrift = False
        else:
            cls.thrift = cls._parse_connection_arg()

        obj = cls._get_object(
            hostname,
            force_ssh,
            skip_health_check,
            user,
            password,
            allow_agent,
            force_thrift,
            local_mode,
            sudo,
            port,
        )
        return obj

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def _get_object(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        hostname,
        # pyre-fixme[2]: Parameter must be annotated.
        force_ssh,
        # pyre-fixme[2]: Parameter must be annotated.
        skip_health_check,
        # pyre-fixme[2]: Parameter must be annotated.
        user,
        # pyre-fixme[2]: Parameter must be annotated.
        password,
        # pyre-fixme[2]: Parameter must be annotated.
        allow_agent,
        # pyre-fixme[2]: Parameter must be annotated.
        force_thrift,
        # pyre-fixme[2]: Parameter must be annotated.
        local_mode,
        # pyre-fixme[2]: Parameter must be annotated.
        sudo,
        # pyre-fixme[2]: Parameter must be annotated.
        port,
    ):
        if local_mode:
            return LocalConn(hostname, sudo=sudo)

        if force_ssh:
            use_thrift = False
        # pyre-fixme[16]: `ConnectionFactory` has no attribute `thrift`.
        elif cls.thrift or force_thrift:
            use_thrift = True
        else:
            use_thrift = False
        if use_thrift:
            return PluginManager.get_plugin_cls("thrift_conn")(
                hostname, port, skip_health_check, sudo=sudo
            )

        return SSHConn(
            hostname,
            skip_health_check,
            user=user,
            password=password,
            allow_agent=allow_agent,
            sudo=sudo,
        )

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    def validate(
        cls,
        # pyre-fixme[2]: Parameter must be annotated.
        hostname,
        # pyre-fixme[2]: Parameter must be annotated.
        user=None,
        # pyre-fixme[2]: Parameter must be annotated.
        password=None,
        allow_agent: bool = False,
    ):
        status = SSHConn(
            hostname,
            user=None,
            password=password,
            allow_agent=allow_agent,
            sudo=False,
        ).ssh_connect()
        return status
