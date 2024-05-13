import datetime
import re
import time
from enum import Enum
from typing import List

from autoval.lib.host.credentials import Credentials
from autoval.lib.test_args import TEST_CONTROL
from autoval.lib.utils.autoval_exceptions import AutoValException, TestError
from autoval.lib.utils.autoval_utils import AutovalLog, AutovalUtils

from autoval.lib.utils.decorators import retry
from autoval.lib.utils.result_handler import ResultHandler


class FioTrigger(Enum):
    """Fio trigger Enum class."""

    WARM_CYCLE = "warm"
    AC_30S_CYCLE = "30s_ac_cycle"
    GRACEFUL_30S_CYCLE = "graceful_30s_cycle"
    AC_CYCLE = "ac"
    DC_CYCLE = "dc"
    SLED_CYCLE = "sled-cycle"
    REBOOT = "reboot"


class BMC:
    """
    This class represents a BMC (Baseboard Management Controller) and provides methods to interact with it.
    """

    CRITICAL_SERVICES_MIN_UPTIME = 120

    def __init__(self, connection, host) -> None:
        self.__connection = connection
        self.hostname = self.__connection.hostname
        self.host = host
        self.oob_addr = host.connection_obj.host_dict.get("oob_addr")
        if self.oob_addr:
            self.bmc_host = self.host.connection_obj._bmc_connections[0]
        else:
            self.bmc_host = self.host.localhost

    def __getattr__(self, name):
        return getattr(self.__connection, name)

    def get_fru_name(self) -> str:
        """
        Extracts the fru name from the help message of the power-util command.
        Returns:
            str: The extracted fru name.
        Raises:
            ValueError: If the fru name could not be determined.
        """
        fru = ""
        slot_info = TEST_CONTROL.get("slot_info", None)
        if slot_info:
            fru = slot_info
            return fru
        power_util_help = self.run_get_result(
            cmd="/usr/local/bin/power-util", ignore_status=True
        ).stdout
        AutovalLog.log_info(f"power-util help: {power_util_help}")
        power_util_help = power_util_help.splitlines()[0]
        pattern = r"\[ (.*?) \]"
        match = re.search(pattern, power_util_help)
        if match:
            fru = match.group(1)
        if "slot" in fru:
            fru = self._get_slot()
        if not fru:
            raise ValueError(
                f"Could not determine fru name. power-util help: {power_util_help}"
            )
        return fru

    def _get_slot(self) -> str:
        slot_details = self.run(f"/usr/local/bin/slot-util {self.host.hostname}")
        slot_number = slot_details.splitlines()[1].strip().split(":")[0]
        return slot_number

    def power_status(self) -> str:
        """
        Gets the power status.
        Returns:
            str: The power status of the FRU.
        """
        cmd = f"/usr/local/bin/power-util {self.get_fru_name()} status"
        status = self.run(cmd)
        return status

    def power_on(self, timeout: int = 1200) -> None:
        """
        Powers on.
        Args:
            timeout (int, optional): The maximum time to wait for power on. Defaults to 1200.
        Returns:
            None
        Raises:
            AutoValException: If fails to power on.
        """
        cmd = f"/usr/local/bin/power-util {self.get_fru_name()} on"
        start_time = time.time()
        self.run(cmd)
        self.wait_for_reconnect(timeout=timeout)
        end_time = time.time()
        ResultHandler().add_cmd_metric(
            "Reconnected after %s" % cmd, start_time, end_time - start_time, 0, ""
        )
        if not self.is_powered_on():
            raise AutoValException("Failed to power on {self.fru}")

    @retry(tries=3, sleep_seconds=10)
    def is_powered_on(self) -> bool:
        """
        Checks if the system is powered on.
        This method attempts to retrieve the power status of the system and checks if it is powered on.
        Returns:
            bool: True if the system is powered on, False otherwise.
        Raises:
            RuntimeError: If the system is not powered on.
        """
        status = self.power_status().upper()
        if "ON" in status:
            return True
        raise RuntimeError(f"{self.fru} is not powered on")

    def check_health(self) -> None:
        """
        Checks the health of the system by attempting to reconnect and checking critical services.
        Returns:
            None
        Raises:
            AutoValException: If the reconnection or service check fails, or if the health check does not pass.
        """
        try:
            self.reconnect()  # Should have been named connect?
            self.check_services(self.get_critical_services())
            passed = True
        except Exception as exc:
            passed = False
            raise AutoValException(
                f"Health check failed on BMC {self.hostname}",
            ) from exc
        finally:
            AutovalUtils.validate_equal(
                passed,
                True,
                f"BMC {self.hostname} health check passed",
                log_on_pass=False,
            )

    def check_services(self, services: List[str]) -> None:
        """
        Checks that all critical services are running and have been running for at least CRITICAL_SERVICES_MIN_UPTIME seconds.
        Returns:
            None
        Raises:
            AutoValException: If any critical service is not running or has not been running for at least CRITICAL_SERVICES_MIN_UPTIME seconds.
        """
        for service in services:
            self.check_service_uptime(service, self.CRITICAL_SERVICES_MIN_UPTIME)

    @retry(tries=10, sleep_seconds=10)
    def check_service_uptime(self, service: str, expected_uptime: int) -> None:
        """
        Checks that the uptime of a given service is >= expected uptime. If service is not running, it will be started.
        Args:
            service (str): The name of the service to check.
            expected_uptime (int): The expected uptime of the service in seconds.
        Returns:
            None
        Raises:
            AutoValException: If the service is not running or its uptime is less than the expected uptime.
        """
        status = self.run(f"sv status {service}")
        if not status.startswith("run:"):
            self.run(f"sv start {service}")
            raise AutoValException(f"Service {service} is not running: {status}")
        time_match = re.match(r".*\s+(\d+)s", status)
        # pyre-fixme[16]: Optional type has no attribute `group`.
        uptime = time_match.group(1)
        if int(uptime) < expected_uptime:
            raise AutoValException(
                f"Service {service} uptime {uptime} is less than expected uptime {expected_uptime}"
            )

    def get_critical_services(self):
        """
        Returns a list of services that are always expected to
        run on the openBMC
        """
        return ["sensord", "healthd", "fscd", "ipmid"]

    def get_bmc_ipv6_addr(self, interface: str = "eth0"):
        """
        Get the ipv6 address for bmc

        To get the ip address of bmc for the interface provided

        Parameters
        ----------
        interface : String
            To find the ip in interface

        Returns
        -------
        ip_addr : str
            ipv6 addr is returned
        """
        if "%" not in self.oob_addr:
            return self.oob_addr
        out = self.bmc_host.run("ip addr show %s" % interface)
        pattern = re.compile(
            r"inet6\s+([a-z0-9:]+).*(?:scope global|scope global dynamic|scope global deprecated dynamic|scope global dynamic noprefixroute)\s+$",
            re.MULTILINE,
        )
        match = pattern.search(out)
        if match:
            ip_addr = match.group(1)
            AutovalLog.log_info(f"IP of {self.oob_addr} with {interface} is: {ip_addr}")
            return ip_addr
        raise TestError(f"Did not find IP type inet6 in {out}")

    def get_fio_trigger_cmd(self, cmd_type, remote: bool = False) -> str:
        """Return trigger command for FIO"""
        cmd = None
        trigger = "--trigger="

        _, oob_password = Credentials.get_openbmc_credentials(
            self.host.hostname, self.host.oob_addr
        )
        sshpass_cmd = f"sshpass -p {oob_password} "
        sshpass_cmd += "ssh -o StrictHostKeyChecking=no root@%s"
        openbmc_sshPass_cmd = sshpass_cmd % (self.get_bmc_ipv6_addr())
        host_sshPass_cmd = (
            "sshpass ssh -o StrictHostKeyChecking=no root@%s" % self.host.hostname
        )
        if cmd_type == FioTrigger.WARM_CYCLE.value:
            reset_cycle_cmd = self.get_cycle_command()["reset"]
            cmd = f"{trigger}'{openbmc_sshPass_cmd} \"({reset_cycle_cmd})\" &'"
        elif cmd_type == FioTrigger.REBOOT.value:
            cmd = trigger + "'shutdown -r &'"
            if remote:
                cmd = f"{trigger}'{host_sshPass_cmd} \"(shutdown -r)\" &'"
        elif cmd_type == FioTrigger.AC_30S_CYCLE.value:
            off_cmd = self.get_cycle_command()["12V-off"]
            on_cmd = self.get_cycle_command()["12V-on"]
            cmd = f"{trigger}'{openbmc_sshPass_cmd} \"({off_cmd} && sleep 30 && {on_cmd})\" &'"
        elif cmd_type == FioTrigger.GRACEFUL_30S_CYCLE.value:
            off_cmd = self.get_cycle_command()["graceful-shutdown"]
            on_cmd = self.get_cycle_command()["power-on"]
            cmd = f"{trigger}'{openbmc_sshPass_cmd} \"({off_cmd} && sleep 150 && {on_cmd})\" &'"
        elif cmd_type == FioTrigger.AC_CYCLE.value:
            ac_cycle_cmd = self.get_cycle_command()["ac"]
            cmd = f"{trigger}'{openbmc_sshPass_cmd} \"({ac_cycle_cmd})\" &'"
        elif cmd_type == FioTrigger.DC_CYCLE.value:
            dc_cycle_cmd = self.get_cycle_command()["dc"]
            cmd = f"{trigger}'{openbmc_sshPass_cmd} \"({dc_cycle_cmd})\" &'"
        elif cmd_type == FioTrigger.SLED_CYCLE.value:
            sled_cycle_cmd = self.get_cycle_command()["sled-cycle"]
            cmd = f"{trigger}'{openbmc_sshPass_cmd} \"({sled_cycle_cmd})\" &'"
        else:
            raise TestError("No supported trigger command found")
        return cmd

    def get_cycle_command(self, slot_id=None):
        """Return dictionary of cycle commands"""
        boot_dic = {}
        boot_dic["sled-cycle"] = "/usr/local/bin/power-util sled-cycle"
        if slot_id is None:
            slot_id = self.get_fru_name()
        cmd = "/usr/local/bin/power-util %s" % slot_id
        boot_dic["ac"] = cmd + " " + "12V-cycle"
        boot_dic["dc"] = cmd + " " + "cycle"
        boot_dic["power-on"] = cmd + " " + "on"
        boot_dic["power-off"] = cmd + " " + "off"
        boot_dic["power-status"] = cmd + " " + "status"
        boot_dic["12V-on"] = cmd + " " + "12V-on"
        boot_dic["12V-off"] = cmd + " " + "12V-off"
        boot_dic["graceful-shutdown"] = cmd + " " + "graceful-shutdown"
        boot_dic["reset"] = cmd + " " + "reset"
        return boot_dic

    def cycle(
        self,
        timeout: int = 1200,
        reboot_check: bool = True,
        post_health_check: bool = True,
    ) -> None:
        """Execute DC power-cycle"""
        boot_cmd = self.get_cycle_command()
        cmd = boot_cmd["dc"]
        if reboot_check:
            current_reboot = self.host.get_last_reboot()
        else:
            current_reboot = None
        AutovalLog.log_info("Cycling now: %s" % cmd)
        time0 = time.time()
        try:
            self.bmc_host.run(cmd)
        except Exception:
            AutovalLog.log_info(
                "OpenBMC Cycle command failed, trying to reconnect anyhow"
            )
        if post_health_check:
            self.host.system_health_check(current_reboot, timeout)
            time1 = time.time()
            self.result_handler.add_cmd_metric(
                "reconnect after %s" % cmd, time0, time1 - time0, 0, ""
            )
        self.post_cycle_check()

    def ac_cycle(
        self, timeout: int = 1200, reboot_check: bool = True, slot=None
    ) -> str:
        """Execute AC power-cycle"""
        boot_cmd = self.get_cycle_command(slot)
        cmd = boot_cmd["ac"]
        if reboot_check:
            last_reboot = self.host.get_last_reboot()
        else:
            last_reboot = None
        time0 = time.time()
        success = self._try_ac_cycle(cmd)
        if not success:
            # Command failed, system might either be rebooting already or
            # command failed to go through, in this case try again
            try:
                time.sleep(5)
                self.host.reconnect(timeout=timeout)
            except Exception:
                # Host is not accessible, so most likely the cmd went through.
                pass
            else:
                # Host is still accessible, so try again:
                self._try_ac_cycle(cmd)
        self.host.system_health_check(last_reboot, timeout)
        time1 = time.time()
        self.result_handler.add_cmd_metric(
            "reconnect after %s" % cmd, time0, time1 - time0, 0, ""
        )
        self.post_cycle_check()
        if not self.validate_powered_on():
            raise Exception("Failed to power on.")
        return "12V Power cycling fru ..."

    def power_reset(self, timeout: int = 1200) -> None:
        """Execute power-reset"""
        # In OpenBMC sled-cycle, resets OpenBMC and all four slots
        boot_cmd = self.get_cycle_command()
        cmd = boot_cmd["sled-cycle"]
        current_reboot = self.host.get_last_reboot()
        bmc_last_reboot = self.bmc_host.get_last_reboot()
        AutovalLog.log_info("Cycling now: %s" % cmd)
        time0 = time.time()
        try:
            self.bmc_host.run(cmd)
        except Exception:
            # Command will not return status.
            AutovalLog.log_info("%s: No response expected. Trying to reconnect" % cmd)
        self.host.system_health_check(
            current_reboot, timeout, bmc_last_reboot, bmc_reconnect_timeout=180
        )
        time1 = time.time()
        self.result_handler.add_cmd_metric(
            "reconnect after %s" % cmd, time0, time1 - time0, 0, ""
        )
        self.post_cycle_check()

    def _try_ac_cycle(self, cmd) -> bool:
        AutovalLog.log_info("AC Cycling now: %s" % cmd)
        try:
            self.bmc_host.run(cmd)
        except Exception:
            return False
        else:
            return True

    def power_off(self, timeout: float = 600):
        """Execute power-off"""
        boot_cmd = self.get_cycle_command()
        cmd = boot_cmd["power-off"]
        AutovalLog.log_info("Powering OFF now: %s" % cmd)
        time0 = time.time()
        out = self.bmc_host.run(cmd)
        success = 0
        end_time = time.time() + timeout
        while time.time() < end_time:
            # Sleep for some time to let shutdown complete
            time.sleep(10)
            try:
                self.host.ping()
            except Exception:
                success = 1
                break
            else:
                continue
        time1 = time.time()
        self.result_handler.add_cmd_metric(
            "disconnect after %s" % cmd, time0, time1 - time0, 0, ""
        )
        if not success:
            raise Exception("Failed to power down system")
        AutovalLog.log_info("Power Down complete")
        return out

    def graceful_shutdown(self, timeout: float = 600) -> None:
        """Execute graceful shutdown"""
        boot_cmd = self.get_cycle_command()
        cmd = boot_cmd["graceful-shutdown"]
        AutovalLog.log_info("Graceful-shutdown: %s" % cmd)
        self.bmc_host.run(cmd)
        success = 0
        end_time = time.time() + timeout
        while time.time() < end_time:
            time.sleep(10)
            if self.check_powered_on():
                continue
            success = 1
            break
        if not success:
            raise Exception("Failed to shut down the server")
        AutovalLog.log_info("Graceful shutdown complete")

    def reboot(
        self,
        timeout: int = 600,
        filter_errors=None,
        critical_services=None,
        skip_bmc_version_check=None,
    ) -> None:
        """Execute OpenBMC reboot, takes approx 2 mins"""
        current_reboot = self.bmc_host.get_last_reboot()
        _time = datetime.datetime.fromtimestamp(int(current_reboot)).strftime(
            "%Y-%m-%d at %H-%M-%S"
        )
        AutovalLog.log_info("Last reboot time is: [%s]" % _time)
        cmd = "reboot"
        AutovalLog.log_info(f"Rebooting {self.PRODUCT_NAME}: {cmd}")
        time0 = time.time()
        self.bmc_host.run(cmd=cmd)
        self.bmc_health_check(
            current_reboot,
            critical_services=critical_services,
        )
        time1 = time.time()
        self.result_handler.add_cmd_metric(
            "reconnect after %s" % cmd, time0, time1 - time0, 0, ""
        )
        self.post_cycle_check(filter_errors)

    def twelve_volt_off(self, timeout: float = 600, slot=None) -> None:
        """
        The command is 12V off which powers off the
        motherboard
        """
        boot_cmd = self.get_cycle_command(slot)
        cmd = boot_cmd["12V-off"]
        AutovalLog.log_info("Powering OFF (12v) now: %s" % cmd)
        self.bmc_host.run(cmd)
        success = 0
        end_time = time.time() + timeout
        while time.time() < end_time:
            # Sleep for some time to let shutdown complete
            time.sleep(40)
            try:
                self.host.ping()
            except Exception:
                success = 1
                break
            else:
                continue
        if not success:
            raise Exception("Failed to power down system")
        AutovalLog.log_info("Power Down complete")

    def twelve_volt_on(self, timeout: int = 1200, last_reboot=None, slot=None) -> None:
        """
        The command is 12V on which powers on the
        motherboard with the CPU still in the off state
        """
        boot_cmd = self.get_cycle_command(slot)
        cmd = boot_cmd["12V-on"]
        AutovalLog.log_info("Issuing 12V-on now: %s" % cmd)
        time0 = time.time()
        self.bmc_host.run(cmd)
        self.host.system_health_check(last_reboot, timeout)
        time1 = time.time()
        self.result_handler.add_cmd_metric(
            "reconnect after %s" % cmd, time0, time1 - time0, 0, ""
        )

    def ac_on_off_fullcycle(
        self,
        timeout: int = 1200,
        last_reboot: int = None,  # pyre-ignore
        slot: str = None,  # pyre-ignore
    ) -> None:
        """
        This method does AC 12V off and 12V on from oob
        on all the platforms except on tiogapass which does
        not have any of 12V cycle command support.

        Parameters
        ----------
        timeout : Integer
            Dut connect timeout value during the system_health_check
        last_reboot : Integer
            last reboot time of the DUT
        slot : String
             slot no of the openBMC
        """
        self.twelve_volt_off(timeout, slot)
        time.sleep(30)
        self.twelve_volt_on(timeout, last_reboot, slot)

    def hmc_reset(self):
        """
        HMC Reset
        """
        # Check that HMC is reachable
        self.bmc_host.run("ping -c 1 192.168.31.1")
        # HMC Reset
        cmd = "hgxmgr factory-reset"
        self.bmc_host.run(cmd)
        # Delay to start reset
        time.sleep(15)
        self.hmc_has_rebooted()
        AutovalLog.log_info("HMC reset complete")

    def cmos_clear(self, timeout: int = 1200, last_reboot=None):
        """CMOS clear"""
        cmd = "bic-util %s 0xe0 0x25 0x15 0xa0 0x00" % self.get_slot_info()
        AutovalLog.log_info("CMOS Reset %s" % cmd)
        time0 = time.time()
        out = self.bmc_host.run(cmd)
        self.host.system_health_check(last_reboot, timeout)
        time1 = time.time()
        self.result_handler.add_cmd_metric(
            "reconnect after %s" % cmd, time0, time1 - time0, 0, ""
        )
        if not self.validate_powered_on():
            raise TestError("Failed to power on after cmos reset")
        return out

    def power_warm(self) -> None:
        """Execute warm power-cycle"""
        self.power_util_reset()

    def power_util_reset(self, timeout: int = 1200, reboot_check: bool = True) -> None:
        """Execute system reset"""
        boot_cmd = self.get_cycle_command()
        cmd = boot_cmd["reset"]
        AutovalLog.log_info("Cycling now: %s" % cmd)
        time0 = time.time()
        try:
            self.bmc_host.run(cmd)
        except Exception:
            AutovalLog.log_info("%s Reset command failed, trying to reconnect" % cmd)
        self.host.check_system_health()
        time1 = time.time()
        self.result_handler.add_cmd_metric(
            "reconnect after %s" % cmd, time0, time1 - time0, 0, ""
        )
        self.post_cycle_check()

    def post_cycle_check(self, filter_errors=None) -> None:
        """Check post_cycle"""
        return
