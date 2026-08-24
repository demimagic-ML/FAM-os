"""Fail-closed process identity checks for owner-scoped Linux services."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from fam_os.supervisor import ServiceDefinition, ServiceState, ServiceStatus


@dataclass(frozen=True, slots=True)
class LinuxProcessIdentity:
    """Verify the process-bearing portion of a service definition via procfs."""

    proc_root: Path = Path("/proc")

    def matches(
        self, status: ServiceStatus, definition: ServiceDefinition,
    ) -> bool:
        if status.state is not ServiceState.ACTIVE or not status.main_pid:
            return False
        process = self.proc_root / str(status.main_pid)
        try:
            executable = Path(os.readlink(process / "exe")).resolve(strict=True)
            expected_executable = Path(definition.command[0]).resolve(strict=True)
            arguments = _nul_values((process / "cmdline").read_bytes())
            environment = dict(
                item.split("=", 1) for item in _nul_values(
                    (process / "environ").read_bytes(),
                ) if "=" in item
            )
        except (OSError, UnicodeError, ValueError):
            return False
        return (
            executable == expected_executable
            and arguments == definition.command
            and all(environment.get(key) == value for key, value in definition.environment)
        )


def _nul_values(payload: bytes) -> tuple[str, ...]:
    return tuple(
        os.fsdecode(value) for value in payload.split(b"\0") if value
    )
