"""Bounded Hyprland window dispatch operations."""

from __future__ import annotations

import re

from fam_os.adapters.linux.command import SubprocessCommandRunner


_ADDRESS = re.compile(r"^0x[0-9a-fA-F]+$")
_WORKSPACE = re.compile(r"^(?:[1-9][0-9]*|special:[A-Za-z0-9_.-]+)$")


class HyprlandWindowControl:
    def __init__(self, runner=None) -> None:
        self._runner = runner or SubprocessCommandRunner()

    def focus(self, address: str) -> bool:
        _require_address(address)
        return self._runner.run(("hyprctl", "dispatch", "focuswindow", f"address:{address}")) is not None

    def move_to_workspace(self, address: str, workspace: str) -> bool:
        _require_address(address)
        if _WORKSPACE.fullmatch(workspace) is None:
            raise ValueError("invalid Hyprland workspace")
        return self._runner.run((
            "hyprctl", "dispatch", "movetoworkspacesilent",
            f"{workspace},address:{address}",
        )) is not None


def _require_address(address: str) -> None:
    if _ADDRESS.fullmatch(address) is None:
        raise ValueError("invalid Hyprland window address")
