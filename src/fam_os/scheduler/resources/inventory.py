"""Versioned physical host-inventory contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


HOST_INVENTORY_CONTRACT_VERSION = "fam.hardware.inventory/v1alpha1"


def _require_identifier(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_non_negative(name: str, values: tuple[int | None, ...]) -> None:
    if any(value is not None and value < 0 for value in values):
        raise ValueError(f"{name} values cannot be negative")


class AcceleratorKind(str, Enum):
    GPU = "gpu"
    NPU = "npu"


class StorageMedium(str, Enum):
    NVME = "nvme"
    SSD = "ssd"
    HDD = "hdd"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class HostCpuInventory:
    architecture: str
    logical_cpu_ids: tuple[int, ...]
    model: str | None = None
    physical_core_count: int | None = None

    def __post_init__(self) -> None:
        _require_identifier("CPU architecture", self.architecture)
        if not self.logical_cpu_ids:
            raise ValueError("at least one logical CPU is required")
        if any(cpu_id < 0 for cpu_id in self.logical_cpu_ids):
            raise ValueError("logical CPU IDs cannot be negative")
        if len(set(self.logical_cpu_ids)) != len(self.logical_cpu_ids):
            raise ValueError("logical CPU IDs must be unique")
        if self.physical_core_count is not None:
            if self.physical_core_count <= 0:
                raise ValueError("physical_core_count must be positive")
            if self.physical_core_count > len(self.logical_cpu_ids):
                raise ValueError("physical cores cannot exceed logical CPUs")


@dataclass(frozen=True, slots=True)
class HostMemoryInventory:
    total_bytes: int
    available_bytes: int
    swap_total_bytes: int = 0
    swap_free_bytes: int = 0

    def __post_init__(self) -> None:
        _require_non_negative(
            "host memory",
            (self.total_bytes, self.available_bytes, self.swap_total_bytes, self.swap_free_bytes),
        )
        if self.total_bytes == 0:
            raise ValueError("host memory total_bytes must be positive")
        if self.available_bytes > self.total_bytes:
            raise ValueError("available memory cannot exceed total memory")
        if self.swap_free_bytes > self.swap_total_bytes:
            raise ValueError("free swap cannot exceed total swap")


@dataclass(frozen=True, slots=True)
class HostAcceleratorInventory:
    device_id: str
    kind: AcceleratorKind
    name: str
    memory_total_bytes: int | None = None
    driver_version: str | None = None

    def __post_init__(self) -> None:
        _require_identifier("accelerator device_id", self.device_id)
        _require_identifier("accelerator name", self.name)
        _require_non_negative("accelerator memory", (self.memory_total_bytes,))


@dataclass(frozen=True, slots=True)
class HostStorageInventory:
    storage_id: str
    medium: StorageMedium
    capacity_bytes: int
    available_bytes: int
    cache_eligible: bool
    mount_path: str | None = None

    def __post_init__(self) -> None:
        _require_identifier("storage_id", self.storage_id)
        _require_non_negative("host storage", (self.capacity_bytes, self.available_bytes))
        if self.capacity_bytes == 0:
            raise ValueError("storage capacity_bytes must be positive")
        if self.available_bytes > self.capacity_bytes:
            raise ValueError("available storage cannot exceed capacity")
        if self.mount_path is not None and not self.mount_path.strip():
            raise ValueError("mount_path must not be empty when provided")


@dataclass(frozen=True, slots=True)
class HostInventory:
    inventory_id: str
    captured_at: datetime
    operating_system: str
    os_release: str
    cpu: HostCpuInventory
    memory: HostMemoryInventory
    storage: tuple[HostStorageInventory, ...]
    accelerators: tuple[HostAcceleratorInventory, ...] = ()
    contract_version: str = HOST_INVENTORY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_identifier("inventory_id", self.inventory_id)
        _require_identifier("operating_system", self.operating_system)
        _require_identifier("os_release", self.os_release)
        if self.contract_version != HOST_INVENTORY_CONTRACT_VERSION:
            raise ValueError("unsupported host-inventory contract_version")
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        if not self.storage:
            raise ValueError("host inventory requires at least one storage tier")
        self._require_unique_ids()

    def _require_unique_ids(self) -> None:
        accelerator_ids = tuple(item.device_id for item in self.accelerators)
        storage_ids = tuple(item.storage_id for item in self.storage)
        if len(set(accelerator_ids)) != len(accelerator_ids):
            raise ValueError("accelerator device IDs must be unique")
        if len(set(storage_ids)) != len(storage_ids):
            raise ValueError("storage IDs must be unique")
