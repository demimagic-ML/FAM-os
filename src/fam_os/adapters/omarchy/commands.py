"""Shell-free Omarchy and UWSM command construction."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


def uwsm_application_command(
    command: Sequence[str], *, executable: str | None = None,
) -> tuple[str, ...]:
    if not command or any(not isinstance(item, str) or not item for item in command):
        raise ValueError("application command must contain non-empty arguments")
    launcher = executable or shutil.which("uwsm-app") or shutil.which("uwsm")
    if launcher is None:
        raise FileNotFoundError("UWSM application launcher is unavailable")
    if launcher.endswith("uwsm-app"):
        return (launcher, "--", *command)
    return (launcher, "app", "--", *command)


class OmarchyCommandRunner:
    def __init__(self, run: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        self._run = run

    def run(self, command: Sequence[str], *, timeout: float = 30) -> CommandReceipt:
        if not command:
            raise ValueError("command cannot be empty")
        try:
            result = self._run(
                tuple(command), capture_output=True, text=True, check=False,
                timeout=timeout,
            )
        except FileNotFoundError as error:
            return CommandReceipt(tuple(command), 127, "", str(error))
        except subprocess.TimeoutExpired as error:
            return CommandReceipt(tuple(command), 124, error.stdout or "", error.stderr or "timeout")
        return CommandReceipt(
            tuple(command), result.returncode, result.stdout.strip(), result.stderr.strip(),
        )
