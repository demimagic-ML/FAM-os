"""Explicit user-systemd adapter settings."""

from dataclasses import dataclass
from math import isfinite
import re


_APPARMOR_PROFILE = re.compile(r"^[A-Za-z0-9_.:/-]+$")


@dataclass(frozen=True, slots=True)
class SystemdUserSettings:
    systemctl_command: str = "systemctl"
    systemd_run_command: str = "systemd-run"
    timeout_seconds: float = 10.0
    apparmor_profile: str | None = None
    retain_failed_state: bool = False
    stop_grace_seconds: float = 3.0

    def __post_init__(self) -> None:
        commands = (self.systemctl_command, self.systemd_run_command)
        if any(not value or _has_control(value) for value in commands):
            raise ValueError("systemd commands must be safe and non-empty")
        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.apparmor_profile is not None and not _APPARMOR_PROFILE.fullmatch(
            self.apparmor_profile
        ):
            raise ValueError("AppArmor profile name is invalid")
        if type(self.retain_failed_state) is not bool:
            raise ValueError("retain_failed_state must be boolean")
        if not isfinite(self.stop_grace_seconds) or self.stop_grace_seconds <= 0:
            raise ValueError("stop_grace_seconds must be positive")


def _has_control(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)
