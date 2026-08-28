"""Omarchy graphical-session detection and application launch."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Mapping, Sequence

from fam_os.adapters.omarchy.commands import CommandReceipt, uwsm_application_command


@dataclass(frozen=True, slots=True)
class OmarchySession:
    session_type: str
    desktop: tuple[str, ...]
    wayland_display: str | None
    hyprland_signature: str | None
    graphical: bool

    @property
    def is_hyprland(self) -> bool:
        return any(item.casefold() == "hyprland" for item in self.desktop) or bool(
            self.hyprland_signature
        )


def detect_session(environment: Mapping[str, str] | None = None) -> OmarchySession:
    values = os.environ if environment is None else environment
    desktops = tuple(
        item for item in values.get("XDG_CURRENT_DESKTOP", "").split(":") if item
    )
    session_type = values.get("XDG_SESSION_TYPE", "unknown").casefold()
    wayland_display = values.get("WAYLAND_DISPLAY")
    signature = values.get("HYPRLAND_INSTANCE_SIGNATURE")
    return OmarchySession(
        session_type, desktops, wayland_display, signature,
        session_type in {"x11", "wayland"} and bool(
            wayland_display or values.get("DISPLAY")
        ),
    )


class UwsmApplicationLauncher:
    def __init__(self, popen=subprocess.Popen, executable: str | None = None):
        self._popen = popen
        self._executable = executable

    def launch(self, command: Sequence[str]) -> CommandReceipt:
        prepared = uwsm_application_command(command, executable=self._executable)
        try:
            process = self._popen(
                prepared, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
        except OSError as error:
            return CommandReceipt(prepared, 127, "", str(error))
        return CommandReceipt(prepared, 0, str(process.pid), "")
