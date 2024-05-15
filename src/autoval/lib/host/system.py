# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
import time
from typing import Any, Dict, List

from autoval.lib.host.bmc import BMC

from autoval.lib.utils.autoval_exceptions import AutoValException, ConnectionError
from autoval.lib.utils.autoval_log import AutovalLog
from autoval.lib.utils.autoval_utils import AutovalUtils

from autoval.lib.utils.decorators import retry
from autoval.lib.utils.result_handler import ResultHandler
from autoval.lib.utils.site_utils import SiteUtils


class System:
    """
    System class represents a DUT (Device Under Test) and provides methods to interact with it.
    """

    # pyre-fixme[2]: Parameter must be annotated.
    def __init__(self, host) -> None:
        # pyre-fixme[4]: Attribute must be annotated.
        self.connection = host.connection_obj.host_connection
        # pyre-fixme[4]: Attribute must be annotated.
        self.hostname = host.connection_obj.hostname
        self.product_name = "System"
        self.oob = self.bmc = BMC(
            connection=host.connection_obj.bmc_connections[0], host=host
        )
        # pyre-fixme[4]: Attribute must be annotated.
        self.host = host

    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def __getattr__(self, name):
        return getattr(self.connection, name)

    # pyre-fixme[3]: Return type must be annotated.
    def get_expander(self):
        return {}

    def clear_cache(self) -> None:
        """
        Clears the cache on the system.

        This method prepares the system for shutdown by
          - clearing the page cache and
          - ensures that all data in the swap space is written back to RAM,
            so that it can be properly saved to disk during the shutdown process

        Note:  swapon/swapoff depend on the existence of `/etc/fstab`

        Raises:
            CmdError: If either of the commands fails to execute successfully.
        """

        cmd = "test -f /etc/fstab"
        out = self.run_get_result(cmd=cmd, ignore_status=True)
        if out.return_code == 0:
            swap_cmd = "swapoff -a; swapon -a"
        else:
            swap_cmd = (
                "systemctl stop swapvol-swapfile.swap; "
                "systemctl start swapvol-swapfile.swap"
            )
        cmd = f"sync; echo 3>/proc/sys/vm/drop_caches; {swap_cmd}"
        out = self.run(cmd=cmd)

    @classmethod
    # pyre-fixme[2]: Parameter must be annotated.
    def _cycle_host(cls, host, cycle_type) -> None:  # noqa: C901
        if cycle_type == "dc":
            host.oob.cycle()
        elif cycle_type == "ac":
            host.oob.ac_cycle()
        elif cycle_type == "warm":
            host.oob.power_warm()
        elif cycle_type == "sled":
            host.oob.power_reset()
        elif cycle_type == "power_off_on":
            last_reboot = host.get_last_reboot()
            host.oob.power_off()
            host.oob.power_on(last_reboot=last_reboot)
        elif cycle_type == "off":
            host.oob.power_off()
        elif cycle_type == "on":
            host.oob.power_on()
        elif cycle_type == "graceful_shutdown":
            host.oob.graceful_shutdown()
            host.oob.power_on()
        elif cycle_type == "reboot":
            host.inband.reboot(shutdown_cmd=True)
        elif cycle_type == "12v_off":
            host.oob.twelve_volt_off()
        elif cycle_type == "12v_on":
            host.oob.twelve_volt_on()
        elif cycle_type == "12v_off_on":
            host.oob.ac_on_off_fullcycle()
        elif cycle_type == "reset":
            host.oob.power_util_reset()
        elif cycle_type == "hmc_reset":
            host.oob.hmc_reset()
        elif cycle_type == "reset_cmos":
            host.oob.cmos_clear()
        else:
            host.oob.misc_power_util(cycle_type)

    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def cycle_host(cls, host, cycle_type: str, log_boot_variance: bool = False):
        """
        Cycles the host and optionally logs the boot variance before and after the cycle.
        Args:
            host (Host): The host to be cycled.
            cycle_type (str): The type of cycle to be performed.
            log_boot_variance (bool, optional): Whether to log the boot variance or not. Defaults to False.
        Raises:
            AutoValException: If the host cycle fails.
        Example:
            >>> cycle_host(host, "reboot", True)
        """
        boot_time_before_cycle = None
        if log_boot_variance:
            try:
                host.ping()
                # check the boot time before the host cycle
                boot_time_before_cycle, _ = host.get_boot_statistics()
            except Exception as e:
                AutovalLog.log_info(
                    "Unable to get boot time for host %s : %s" % (host.hostname, e)
                )
        try:
            did_pass = True
            cls._cycle_host(host, cycle_type)
        except AutoValException:
            did_pass = False
            raise
        finally:
            boot_statistics = {}
            boot_statistics["type"] = cycle_type
            boot_statistics["did_pass"] = did_pass
            boot_statistics["dut"] = host.hostname
            if log_boot_variance and boot_time_before_cycle:
                if did_pass:
                    try:
                        host.ping()
                        # check the boot time after the host cycle
                        (
                            boot_time_after_cycle,
                            boot_statistics_dict,
                        ) = host.get_boot_statistics()
                        variance = abs(boot_time_after_cycle - boot_time_before_cycle)
                        boot_statistics["boot_metrics"] = boot_statistics_dict
                        boot_statistics["variance"] = variance
                        AutovalLog.log_info(
                            f"{cycle_type} cycle - Boot variance - {variance} sec, {boot_time_before_cycle} sec before the {cycle_type} && {boot_time_after_cycle} sec after the {cycle_type}."
                        )
                    except Exception as e:
                        AutovalLog.log_info(
                            f"log_boot_variance is True. Error in getting the boot statistics for the host {host.hostname} , error : {e}"
                        )
                        raise AutoValException(
                            f"log_boot_variance is True. Error in getting the boot statistics for the host {host.hostname} , error : {e}"
                        )
                cls.save_boot_metrics(boot_statistics)

    @classmethod
    def save_boot_metrics(cls, boot_info: Dict[str, Any]) -> None:
        """
        Saves the boot metrics information in test results.
        Args:
            boot_info (Dict[str, Any]): A dictionary containing the boot metrics information.
        """
        reboots = ResultHandler.test_results.get("reboots", [])
        reboots.append(boot_info)
        ResultHandler.test_results["reboots"] = reboots

    def check_system_health(self) -> None:
        """
        Checks the health of the system and its BMC.
        Returns:
            None
        """
        self.check_health()
        self.oob.check_health()

    # TODO - Not 100% sure if we need it
    def check_connection(self, tries: int, interval: int) -> None:
        for itr in range(tries):
            try:
                time.sleep(interval)
                if itr != tries - 1:
                    self.run("ipmitool mc info")
                    break
            except Exception as exc:
                raise ConnectionError(
                    identifier=self.hostname,
                    message="Could not establish the connection",
                ) from exc

    def check_health(self) -> None:
        """
        Checks the health of the system by verifying the connection and critical systemd services, defined in site settings.
        """
        try:
            self.check_connection(tries=5, interval=30)
            self.check_services(SiteUtils.get_critical_services())
            passed = True
        except Exception as exc:
            passed = False
            raise AutoValException(
                f"Health check failed on {self.hostname}",
            ) from exc
        finally:
            AutovalUtils.validate_equal(
                passed,
                True,
                f"{self.hostname} health check passed",
                log_on_pass=False,
            )

    # pyre-fixme[3]: Return type must be annotated.
    def check_services(self, services: List[str]):
        """
        Checks the status of given list of services.
        Args:
            services (List[str]): A list of service names to check.
        Returns:
            None
        """
        for service in services:
            self.is_service_active(service)

    @retry(tries=40, sleep_seconds=15)
    def is_service_active(self, service: str) -> bool:
        """
        Checks if a specific service is active.
        Args:
            service (str): The name of the service to check.
        Returns:
            bool: True if the service is active, False otherwise.
        Raises:
            AutoValException: If the service is not active after 40 tries with a 15 seconds interval.
        """
        run_obj = self.run_get_result(
            "systemctl is-active --quiet %s" % service,
            ignore_status=True,
        )
        if run_obj.return_code == 0:
            return True
        else:
            raise AutoValException(f"Service {service} not active")
