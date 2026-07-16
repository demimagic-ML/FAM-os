"""Linux adapters for live accelerator and bounded cache observations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.linux.command import CommandRunner
from fam_os.adapters.linux.nvidia import query_nvidia_resources
from fam_os.scheduler.live_ports import (
    AcceleratorUsageReading,
    StorageCacheReading,
)


@dataclass(frozen=True, slots=True)
class NvidiaAcceleratorRuntimeObserver:
    runner: CommandRunner

    def observe_accelerators(self) -> tuple[AcceleratorUsageReading, ...]:
        return tuple(
            AcceleratorUsageReading(
                f"gpu-{reading.index}", reading.memory_used_bytes,
                reading.utilization_fraction,
            )
            for reading in query_nvidia_resources(self.runner)
        )


@dataclass(frozen=True, slots=True)
class CacheDirectory:
    storage_id: str
    path: Path

    def __post_init__(self) -> None:
        if not self.storage_id.strip() or not self.path.is_absolute():
            raise ValueError("cache directory requires an ID and absolute path")


@dataclass(frozen=True, slots=True)
class DirectoryStorageRuntimeObserver:
    directories: tuple[CacheDirectory, ...]
    maximum_entries: int = 100_000

    def __post_init__(self) -> None:
        identities = tuple(item.storage_id for item in self.directories)
        if len(set(identities)) != len(identities):
            raise ValueError("cache storage IDs must be unique")
        if self.maximum_entries <= 0:
            raise ValueError("maximum cache entries must be positive")

    def observe_storage(self) -> tuple[StorageCacheReading, ...]:
        return tuple(
            StorageCacheReading(item.storage_id, _directory_bytes(item.path, self.maximum_entries))
            for item in self.directories
        )


def _directory_bytes(root: Path, maximum_entries: int) -> int:
    if root.is_symlink():
        raise ValueError("cache directory root must not be a symbolic link")
    if not root.exists():
        return 0
    total = 0
    entries = 0
    pending = [root]
    while pending:
        directory = pending.pop()
        for child in directory.iterdir():
            entries += 1
            if entries > maximum_entries:
                raise ValueError("cache directory entry limit exceeded")
            if child.is_symlink():
                continue
            if child.is_dir():
                pending.append(child)
            elif child.is_file():
                total += child.stat().st_size
    return total
