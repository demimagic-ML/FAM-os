"""Privacy-bounded current-user application process discovery from procfs."""

import os
from dataclasses import dataclass
from pathlib import Path

from fam_os.applications import (
    ApplicationDiscoveryIssue, ApplicationProcess, DiscoverySurface,
)


@dataclass(frozen=True, slots=True)
class ProcessDiscoveryResult:
    processes: tuple[ApplicationProcess, ...]
    issues: tuple[ApplicationDiscoveryIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class LinuxProcessDiscoverySettings:
    proc_root: Path = Path("/proc")
    user_id: int = os.getuid()
    maximum_processes: int = 4096

    def __post_init__(self) -> None:
        if self.user_id < 0 or self.maximum_processes <= 0:
            raise ValueError("Linux process discovery settings are invalid")


class LinuxProcessDiscovery:
    def __init__(self, settings=LinuxProcessDiscoverySettings()):
        self._settings = settings

    def discover(self) -> ProcessDiscoveryResult:
        try:
            directories = tuple(sorted(
                (path for path in self._settings.proc_root.iterdir() if path.name.isdigit()),
                key=lambda path: int(path.name),
            ))
        except OSError:
            return ProcessDiscoveryResult((), (_issue("linux.procfs.unavailable"),))
        processes = []
        for directory in directories:
            process = _read_process(directory, self._settings.user_id)
            if process is not None:
                processes.append(process)
            if len(processes) >= self._settings.maximum_processes:
                return ProcessDiscoveryResult(
                    tuple(processes), (_issue("linux.procfs.process_limit"),)
                )
        return ProcessDiscoveryResult(tuple(processes))


def parse_process_stat(content: str) -> tuple[int, str, int, int]:
    opening = content.find("(")
    closing = content.rfind(")")
    if opening <= 0 or closing <= opening:
        raise ValueError("proc stat record is malformed")
    process_id = int(content[:opening].strip())
    command_name = content[opening + 1:closing]
    fields = content[closing + 1:].strip().split()
    if len(fields) < 20:
        raise ValueError("proc stat record is incomplete")
    return process_id, command_name, int(fields[1]), int(fields[19])


def parse_process_user_id(content: str) -> int:
    for line in content.splitlines():
        if line.startswith("Uid:"):
            return int(line.split()[1])
    raise ValueError("proc status has no user identity")


def _read_process(directory: Path, required_user_id: int):
    try:
        user_id = parse_process_user_id(_read_bounded(directory / "status"))
        if user_id != required_user_id:
            return None
        process_id, command_name, parent_id, start_ticks = parse_process_stat(
            _read_bounded(directory / "stat")
        )
        try:
            executable_name = (directory / "exe").resolve(strict=True).name
        except OSError:
            executable_name = command_name
        return ApplicationProcess(
            process_id, parent_id, user_id, executable_name,
            command_name, start_ticks,
        )
    except (OSError, ValueError, IndexError):
        return None


def _read_bounded(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        return stream.read(16_384)


def _issue(code):
    return ApplicationDiscoveryIssue(
        DiscoverySurface.PROCESSES, code,
        "Application process discovery is incomplete.",
    )
