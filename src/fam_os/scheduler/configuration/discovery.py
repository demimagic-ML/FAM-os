"""Versioned discovered and enforced runtime resource state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fam_os.scheduler.resources import HostInventory, PressureReading
from fam_os.scheduler.configuration.policy import CONFIGURATION_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class AcceleratorRuntimeState:
    device_id: str
    current_memory_bytes: int

    def __post_init__(self) -> None:
        if not self.device_id.strip() or self.current_memory_bytes < 0:
            raise ValueError("accelerator runtime state is invalid")


@dataclass(frozen=True, slots=True)
class StorageRuntimeState:
    storage_id: str
    current_cache_bytes: int

    def __post_init__(self) -> None:
        if not self.storage_id.strip() or self.current_cache_bytes < 0:
            raise ValueError("storage runtime state is invalid")


@dataclass(frozen=True, slots=True)
class DiscoveredResourceState:
    state_id: str
    captured_at: datetime
    inventory: HostInventory
    memory_current_bytes: int
    swap_limit_bytes: int
    swap_current_bytes: int
    cgroup_cpu_quota_cores: float | None = None
    cgroup_memory_limit_bytes: int | None = None
    accelerators: tuple[AcceleratorRuntimeState, ...] = ()
    storage: tuple[StorageRuntimeState, ...] = ()
    pressure: tuple[PressureReading, ...] = ()
    contract_version: str = CONFIGURATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.state_id.strip():
            raise ValueError("state_id must not be empty")
        if self.contract_version != CONFIGURATION_CONTRACT_VERSION:
            raise ValueError("unsupported discovery contract_version")
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        values = (
            self.memory_current_bytes,
            self.swap_limit_bytes,
            self.swap_current_bytes,
            self.cgroup_memory_limit_bytes,
        )
        if any(value is not None and value < 0 for value in values):
            raise ValueError("discovered resource values cannot be negative")
        if self.cgroup_cpu_quota_cores is not None and self.cgroup_cpu_quota_cores <= 0:
            raise ValueError("cgroup CPU quota must be positive")
        self._validate_resource_ids()

    def _validate_resource_ids(self) -> None:
        accelerator_ids = tuple(item.device_id for item in self.accelerators)
        storage_ids = tuple(item.storage_id for item in self.storage)
        if len(set(accelerator_ids)) != len(accelerator_ids):
            raise ValueError("accelerator runtime IDs must be unique")
        if len(set(storage_ids)) != len(storage_ids):
            raise ValueError("storage runtime IDs must be unique")
        known_accelerators = {item.device_id for item in self.inventory.accelerators}
        known_storage = {item.storage_id for item in self.inventory.storage}
        if not set(accelerator_ids) <= known_accelerators:
            raise ValueError("runtime accelerator must exist in inventory")
        if not set(storage_ids) <= known_storage:
            raise ValueError("runtime storage must exist in inventory")
