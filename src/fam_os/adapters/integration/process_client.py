"""Bounded no-shell client for trusted systemd and Bubblewrap commands."""

from dataclasses import dataclass
import os
from pathlib import Path
import stat
import subprocess

from fam_os.adapters.linux.bounded_command import BoundedCommandPolicy, BoundedSubprocessRunner


@dataclass(frozen=True, slots=True)
class ProcessCommandResult:
    exit_code: int
    output: str


class ProcessCommandClient:
    def __init__(self, systemd_run=Path("/usr/bin/systemd-run"),
                 systemctl=Path("/usr/bin/systemctl"), bubblewrap=Path("/usr/bin/bwrap")):
        for path in (systemd_run, systemctl, bubblewrap):
            _trusted_executable(path)
        self.systemd_run, self.systemctl, self.bubblewrap = systemd_run, systemctl, bubblewrap
        self._runner = BoundedSubprocessRunner(BoundedCommandPolicy(
            timeout_seconds=30, maximum_stdout_bytes=262_144, maximum_stderr_bytes=262_144,
        ))

    def run(self, executable: Path, arguments: tuple[str, ...]) -> ProcessCommandResult:
        environment = _environment()
        result = self._runner.run((str(executable), *arguments), environment=environment)
        return ProcessCommandResult(
            -1 if result.exit_code is None else result.exit_code,
            result.stdout + result.stderr,
        )

    def start_scope(self, arguments: tuple[str, ...]):
        if not arguments or any(not isinstance(item, str) or "\0" in item for item in arguments):
            raise ValueError("process scope command is invalid")
        return subprocess.Popen(
            (str(self.systemd_run), *arguments), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True, start_new_session=True, env=_environment(),
        )


def _trusted_executable(path: Path) -> None:
    details = path.stat(follow_symlinks=False)
    if (not path.is_absolute() or path.is_symlink() or not stat.S_ISREG(details.st_mode)
            or details.st_uid != 0 or details.st_mode & 0o022 or not os.access(path, os.X_OK)):
        raise PermissionError("integration executable must be immutable and root-owned")


def _environment():
    value = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    for name in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
        if name in os.environ:
            value[name] = os.environ[name]
    return value
