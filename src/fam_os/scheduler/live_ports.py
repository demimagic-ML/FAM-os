"""Replaceable current accelerator and scheduler-cache observation ports."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AcceleratorUsageReading:
    device_id: str
    current_memory_bytes: int
    utilization_fraction: float | None = None

    def __post_init__(self) -> None:
        if not self.device_id.strip() or self.current_memory_bytes < 0:
            raise ValueError("accelerator usage reading is invalid")
        if self.utilization_fraction is not None and not 0 <= self.utilization_fraction <= 1:
            raise ValueError("accelerator utilization must be between zero and one")


@dataclass(frozen=True, slots=True)
class StorageCacheReading:
    storage_id: str
    current_cache_bytes: int

    def __post_init__(self) -> None:
        if not self.storage_id.strip() or self.current_cache_bytes < 0:
            raise ValueError("storage cache reading is invalid")


class AcceleratorRuntimeObserver(Protocol):
    def observe_accelerators(self) -> tuple[AcceleratorUsageReading, ...]: ...


class StorageRuntimeObserver(Protocol):
    def observe_storage(self) -> tuple[StorageCacheReading, ...]: ...
