#!/usr/bin/env python3

import datetime

from autoval.lib.utils.autoval_log import AutovalLog
from autoval.plugins.plugin_manager import PluginManager


class Manifest:
    # pyre-fixme[3]: Return type must be annotated.
    def get_test_manifest(self):
        manifest = {
            "version": "<unknown>",
            "revision": "<unknown>",
            "revision_epochtime": "<unknown>",
        }

        try:
            import __manifest__
        except Exception:
            AutovalLog.log_info("Failed to collect test manifest data")
            return manifest

        fbmake = __manifest__.fbmake
        manifest["build_time"] = fbmake.get("time", "<unknown>")
        manifest["version"] = fbmake.get("version", "<unknown>")
        manifest["release"] = fbmake.get("release", "<unknown>")
        manifest["revision"] = fbmake.get("revision", "<unknown>")
        manifest["revision_epochtime"] = fbmake.get("revision_epochtime", "<unknown>")
        manifest["revision_time"] = self._get_time_str(manifest["revision_epochtime"])

        if manifest["version"] not in ("<unknown>", "") and manifest["release"] in (
            "<unknown>",
            "",
        ):
            try:
                release, buildtime = PluginManager.get_plugin_cls(
                    "release_manager_plugin"
                )().get_release_and_buildtime(pkg_version=manifest["version"])
                if release:
                    manifest["release"] = release
                if buildtime:
                    manifest["build_time"] = self._get_time_str(buildtime)
            except Exception:
                manifest["release"] = "<unknown>"

        return manifest

    # pyre-fixme[2]: Parameter must be annotated.
    def _get_time_str(self, epoch) -> str:
        datetime_str = datetime.datetime.fromtimestamp(int(epoch)).strftime("%c")
        return datetime_str
