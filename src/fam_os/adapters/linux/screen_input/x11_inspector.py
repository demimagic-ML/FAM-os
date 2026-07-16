"""Bounded shell-free X11 active-window and geometry inspection."""

import re
from dataclasses import dataclass

from fam_os.adapters.linux.bounded_command import (
    BoundedCommandPolicy, BoundedSubprocessRunner,
)
from fam_os.adapters.linux.screen_input.types import ProviderWindowState
from fam_os.applications import ScreenTarget


_WINDOW = re.compile(r"^0x[0-9a-fA-F]+$")
_ACTIVE = re.compile(r"window id # (0x[0-9a-fA-F]+)")
_PID = re.compile(r"_NET_WM_PID\([^)]*\)\s*=\s*(\d+)")


@dataclass(frozen=True, slots=True)
class X11InspectorSettings:
    session_type: str
    display: str
    xprop_path: str = "/usr/bin/xprop"
    xwininfo_path: str = "/usr/bin/xwininfo"


class X11WindowInspector:
    def __init__(self, settings: X11InspectorSettings, runner=None):
        self._settings = settings
        self._runner = runner or BoundedSubprocessRunner(
            BoundedCommandPolicy(1.0, 64 * 1024, 16 * 1024)
        )

    def available(self) -> bool:
        return self._settings.session_type.casefold() == "x11" and bool(self._settings.display)

    def inspect(self, target: ScreenTarget) -> ProviderWindowState | None:
        if not self.available() or _WINDOW.fullmatch(target.window_id) is None:
            return None
        active = self._run((self._settings.xprop_path, "-root", "_NET_ACTIVE_WINDOW"))
        properties = self._run((
            self._settings.xprop_path, "-id", target.window_id, "_NET_WM_PID",
        ))
        geometry = self._run((self._settings.xwininfo_path, "-id", target.window_id))
        if None in (active, properties, geometry):
            return None
        return parse_window_state(target.window_id, active, properties, geometry)

    def _run(self, command):
        result = self._runner.run(command, environment={
            "DISPLAY": self._settings.display, "LANG": "C", "LC_ALL": "C",
        })
        return result.stdout if result.succeeded else None


def parse_window_state(window_id, active_output, property_output, geometry_output):
    active_match = _ACTIVE.search(active_output)
    pid_match = _PID.search(property_output)
    values = {
        key: _integer(geometry_output, label)
        for key, label in (
            ("x", "Absolute upper-left X"), ("y", "Absolute upper-left Y"),
            ("width", "Width"), ("height", "Height"),
        )
    }
    if active_match is None or pid_match is None or None in values.values():
        return None
    if "Map State: IsViewable" not in geometry_output:
        return None
    return ProviderWindowState(
        window_id, int(pid_match.group(1)), values["x"], values["y"],
        values["width"], values["height"],
        int(active_match.group(1), 16) == int(window_id, 16),
    )


def _integer(output, label):
    match = re.search(rf"^\s*{re.escape(label)}:\s*(-?\d+)\s*$", output, re.MULTILINE)
    return int(match.group(1)) if match is not None else None
