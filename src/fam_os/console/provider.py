"""Local provider that assembles complete visibility without granting authority."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fam_os.console.contracts import ConsoleItem, ConsoleSection, ConsoleSnapshot


class LocalConsoleProvider:
    def __init__(self, state_root: Path, release_id: str = "development") -> None:
        self._state_root = state_root
        self._release_id = release_id

    def snapshot(self) -> ConsoleSnapshot:
        return ConsoleSnapshot(
            datetime.now(timezone.utc), os.geteuid(), self._release_id,
            (self._resources(), self._experts(), self._permissions(),
             self._memory(), self._audit(), self._recovery()),
            (self._state_root / "recovery" / "enabled").is_file(),
        )

    def _resources(self) -> ConsoleSection:
        memory = _memory_available()
        disk = shutil.disk_usage(self._state_root)
        items = (
            ConsoleItem("cpu", "Logical CPUs", str(os.cpu_count() or 1), "healthy"),
            ConsoleItem("memory", "Available memory", _bytes(memory), "healthy"),
            ConsoleItem("storage", "Available storage", _bytes(disk.free), "healthy"),
        )
        return ConsoleSection("resources", "Resources", items)

    def _experts(self) -> ConsoleSection:
        return _file_section(self._state_root / "experts", "experts", "Experts")

    def _permissions(self) -> ConsoleSection:
        return _file_section(self._state_root / "permissions", "permissions", "Permissions")

    def _memory(self) -> ConsoleSection:
        return _file_section(self._state_root / "memory", "memory", "Memory")

    def _audit(self) -> ConsoleSection:
        return _file_section(self._state_root / "audit", "audit", "Audit history")

    def _recovery(self) -> ConsoleSection:
        enabled = (self._state_root / "recovery" / "enabled").is_file()
        item = ConsoleItem(
            "mode", "Recovery mode", "Enabled" if enabled else "Ready",
            "attention" if enabled else "healthy",
            "Offline controls only" if enabled else "Normal operation",
        )
        return ConsoleSection("recovery", "Recovery", (item,))


def _file_section(path: Path, section_id: str, title: str) -> ConsoleSection:
    if not path.exists():
        item = ConsoleItem("state", "Local state", "Not initialized", "unavailable",
                           "No data has been published by the owning service")
        return ConsoleSection(section_id, title, (item,))
    entries = sum(1 for item in path.rglob("*") if item.is_file())
    item = ConsoleItem("state", "Local records", str(entries), "healthy")
    return ConsoleSection(section_id, title, (item,))


def _memory_available() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    return 0


def _bytes(value: int) -> str:
    return f"{value / (1024 ** 3):.1f} GiB"
