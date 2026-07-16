"""Bounded, shell-free command execution for read-only probes."""

from __future__ import annotations

import subprocess
from typing import Protocol


class CommandRunner(Protocol):
    def run(self, command: tuple[str, ...], timeout_seconds: float = 10.0) -> str | None: ...


class SubprocessCommandRunner:
    def run(self, command: tuple[str, ...], timeout_seconds: float = 10.0) -> str | None:
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return None
        return result.stdout.strip()

