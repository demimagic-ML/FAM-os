"""Aggregate Linux process I/O counters for one service cgroup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProcessIoReading:
    physical_read_bytes: int
    physical_write_bytes: int
    logical_read_bytes: int
    logical_write_bytes: int
    process_count: int


@dataclass(frozen=True, slots=True)
class CgroupProcessIoObserver:
    cgroup_root: Path = Path("/sys/fs/cgroup")
    proc_root: Path = Path("/proc")

    def observe(self, control_group: str) -> ProcessIoReading:
        group = self.cgroup_root / control_group.removeprefix("/")
        processes = _processes(group)
        counters = {name: 0 for name in ("read_bytes", "write_bytes", "rchar", "wchar")}
        observed = 0
        for process in processes:
            try:
                values = _parse_io((self.proc_root / str(process) / "io").read_text())
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
            observed += 1
            for name in counters:
                counters[name] += values.get(name, 0)
        return ProcessIoReading(
            counters["read_bytes"], counters["write_bytes"],
            counters["rchar"], counters["wchar"], observed,
        )


def _processes(group: Path) -> tuple[int, ...]:
    try:
        return tuple(int(value) for value in (group / "cgroup.procs").read_text().split())
    except FileNotFoundError:
        return ()


def _parse_io(content: str) -> dict[str, int]:
    values = {}
    for line in content.splitlines():
        name, raw = line.split(":", 1)
        value = int(raw.strip())
        if value < 0:
            raise ValueError("process I/O counter cannot be negative")
        values[name] = value
    return values
