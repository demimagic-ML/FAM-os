"""Versioned effective resource-budget contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fam_os.scheduler.resources.identity import (
    COMPAT_CPU_16GB_PROFILE_ID,
    ValidationProfileRef,
)
from fam_os.scheduler.resources.pressure import PressureReading


EFFECTIVE_RESOURCE_BUDGET_CONTRACT_VERSION = "fam.hardware.budget/v1alpha1"


def _require_fraction(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between zero and one")


@dataclass(frozen=True, slots=True)
class CpuResourceBudget:
    visible_logical_cpu_ids: tuple[int, ...]
    schedulable_logical_cpu_ids: tuple[int, ...]
    reserved_logical_cpu_ids: tuple[int, ...]
    scheduler_quota_cores: float
    current_utilization_fraction: float
    cgroup_quota_cores: float | None = None

    def __post_init__(self) -> None:
        visible = set(self.visible_logical_cpu_ids)
        schedulable = set(self.schedulable_logical_cpu_ids)
        reserved = set(self.reserved_logical_cpu_ids)
        if not visible or not schedulable:
            raise ValueError("CPU budget requires visible and schedulable CPUs")
        if min(visible) < 0:
            raise ValueError("logical CPU IDs cannot be negative")
        if len(visible) != len(self.visible_logical_cpu_ids):
            raise ValueError("visible logical CPU IDs must be unique")
        if len(schedulable) != len(self.schedulable_logical_cpu_ids):
            raise ValueError("schedulable logical CPU IDs must be unique")
        if len(reserved) != len(self.reserved_logical_cpu_ids):
            raise ValueError("reserved logical CPU IDs must be unique")
        if not (schedulable | reserved) <= visible or schedulable & reserved:
            raise ValueError("schedulable and reserved CPUs must be disjoint visible CPUs")
        self._validate_quotas(len(schedulable))
        _require_fraction("current_utilization_fraction", self.current_utilization_fraction)

    def _validate_quotas(self, schedulable_count: int) -> None:
        if not 0 < self.scheduler_quota_cores <= schedulable_count:
            raise ValueError("scheduler_quota_cores exceeds schedulable CPUs")
        if self.cgroup_quota_cores is not None:
            if self.cgroup_quota_cores <= 0:
                raise ValueError("cgroup_quota_cores must be positive")
            if self.scheduler_quota_cores > self.cgroup_quota_cores:
                raise ValueError("scheduler CPU quota cannot exceed cgroup quota")


@dataclass(frozen=True, slots=True)
class MemoryResourceBudget:
    effective_limit_bytes: int
    scheduler_limit_bytes: int
    reserved_headroom_bytes: int
    current_bytes: int
    swap_limit_bytes: int
    swap_current_bytes: int
    cgroup_limit_bytes: int | None = None

    def __post_init__(self) -> None:
        values = (
            self.effective_limit_bytes,
            self.scheduler_limit_bytes,
            self.reserved_headroom_bytes,
            self.current_bytes,
            self.swap_limit_bytes,
            self.swap_current_bytes,
        )
        if any(value < 0 for value in values):
            raise ValueError("memory budget values cannot be negative")
        if self.effective_limit_bytes == 0 or self.scheduler_limit_bytes == 0:
            raise ValueError("effective and scheduler memory limits must be positive")
        if self.scheduler_limit_bytes + self.reserved_headroom_bytes > self.effective_limit_bytes:
            raise ValueError("scheduler memory limit and headroom exceed effective limit")
        if self.cgroup_limit_bytes is not None:
            if self.cgroup_limit_bytes <= 0:
                raise ValueError("cgroup memory limit must be positive")
            if self.effective_limit_bytes > self.cgroup_limit_bytes:
                raise ValueError("effective memory limit cannot exceed cgroup limit")

    @property
    def available_for_new_bytes(self) -> int:
        return max(0, self.scheduler_limit_bytes - self.current_bytes)


@dataclass(frozen=True, slots=True)
class AcceleratorResourceBudget:
    device_id: str
    placement_allowed: bool
    effective_memory_limit_bytes: int
    scheduler_memory_limit_bytes: int
    reserved_memory_bytes: int
    current_memory_bytes: int

    def __post_init__(self) -> None:
        if not self.device_id.strip():
            raise ValueError("accelerator device_id must not be empty")
        values = (
            self.effective_memory_limit_bytes,
            self.scheduler_memory_limit_bytes,
            self.reserved_memory_bytes,
            self.current_memory_bytes,
        )
        if any(value < 0 for value in values):
            raise ValueError("accelerator budget values cannot be negative")
        if self.scheduler_memory_limit_bytes + self.reserved_memory_bytes > self.effective_memory_limit_bytes:
            raise ValueError("accelerator scheduler limit and reserve exceed effective limit")
        if self.placement_allowed and self.scheduler_memory_limit_bytes == 0:
            raise ValueError("allowed accelerator placement requires a memory budget")
        if not self.placement_allowed and self.scheduler_memory_limit_bytes != 0:
            raise ValueError("disallowed accelerator placement must have zero scheduler memory")


@dataclass(frozen=True, slots=True)
class StorageResourceBudget:
    storage_id: str
    effective_cache_limit_bytes: int
    scheduler_cache_limit_bytes: int
    reserved_free_bytes: int
    current_cache_bytes: int
    read_limit_bytes_per_second: int | None = None
    write_limit_bytes_per_second: int | None = None

    def __post_init__(self) -> None:
        if not self.storage_id.strip():
            raise ValueError("storage_id must not be empty")
        values = (
            self.effective_cache_limit_bytes,
            self.scheduler_cache_limit_bytes,
            self.reserved_free_bytes,
            self.current_cache_bytes,
        )
        if any(value < 0 for value in values):
            raise ValueError("storage budget values cannot be negative")
        if self.scheduler_cache_limit_bytes + self.reserved_free_bytes > self.effective_cache_limit_bytes:
            raise ValueError("storage cache limit and reserve exceed effective limit")
        for rate in (self.read_limit_bytes_per_second, self.write_limit_bytes_per_second):
            if rate is not None and rate <= 0:
                raise ValueError("storage I/O limits must be positive when provided")


@dataclass(frozen=True, slots=True)
class EffectiveResourceBudget:
    budget_id: str
    inventory_id: str
    captured_at: datetime
    validation_profile: ValidationProfileRef
    cpu: CpuResourceBudget
    memory: MemoryResourceBudget
    accelerators: tuple[AcceleratorResourceBudget, ...]
    storage: tuple[StorageResourceBudget, ...]
    pressure: tuple[PressureReading, ...] = ()
    contract_version: str = EFFECTIVE_RESOURCE_BUDGET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.budget_id.strip() or not self.inventory_id.strip():
            raise ValueError("budget_id and inventory_id must not be empty")
        if self.contract_version != EFFECTIVE_RESOURCE_BUDGET_CONTRACT_VERSION:
            raise ValueError("unsupported effective-resource-budget contract_version")
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        if not self.storage:
            raise ValueError("effective resource budget requires a storage budget")
        self._require_unique_resource_ids()
        self._require_known_pressure_resources()
        if self.validation_profile.profile_id == COMPAT_CPU_16GB_PROFILE_ID:
            if any(item.placement_allowed for item in self.accelerators):
                raise ValueError("compat-cpu-16gb cannot allow accelerator placement")

    def _require_unique_resource_ids(self) -> None:
        accelerator_ids = tuple(item.device_id for item in self.accelerators)
        storage_ids = tuple(item.storage_id for item in self.storage)
        pressure_ids = tuple(item.resource_id for item in self.pressure)
        if len(set(accelerator_ids)) != len(accelerator_ids):
            raise ValueError("accelerator budget IDs must be unique")
        if len(set(storage_ids)) != len(storage_ids):
            raise ValueError("storage budget IDs must be unique")
        if len(set(pressure_ids)) != len(pressure_ids):
            raise ValueError("pressure resource IDs must be unique")

    def _require_known_pressure_resources(self) -> None:
        known = {"cpu", "memory"}
        known.update(item.device_id for item in self.accelerators)
        known.update(item.storage_id for item in self.storage)
        unknown = {item.resource_id for item in self.pressure} - known
        if unknown:
            raise ValueError(f"pressure references unknown resources: {sorted(unknown)}")
