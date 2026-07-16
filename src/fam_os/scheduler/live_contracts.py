"""Versioned repeated live resource observations for scheduler decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


LIVE_RESOURCE_OBSERVATION_VERSION = "fam.scheduler.live-resources/v1alpha1"


class ObservationStatus(StrEnum):
    BASELINE = "baseline"
    COMPLETE = "complete"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class LiveCpuAvailability:
    scheduler_quota_cores: float
    cgroup_quota_cores: float | None
    interval_seconds: float | None
    usage_delta_microseconds: int | None
    utilization_fraction: float | None
    usage_total_microseconds: int | None

    def __post_init__(self) -> None:
        if self.scheduler_quota_cores <= 0:
            raise ValueError("live scheduler CPU quota must be positive")
        if self.cgroup_quota_cores is not None and self.cgroup_quota_cores <= 0:
            raise ValueError("live cgroup CPU quota must be positive")
        paired = (self.interval_seconds is None) == (self.usage_delta_microseconds is None)
        if not paired or (self.interval_seconds is None) != (self.utilization_fraction is None):
            raise ValueError("live CPU delta measurements must be present together")
        if self.interval_seconds is not None and self.interval_seconds <= 0:
            raise ValueError("live CPU interval must be positive")
        if self.usage_delta_microseconds is not None and self.usage_delta_microseconds < 0:
            raise ValueError("live CPU usage delta must not be negative")
        if self.utilization_fraction is not None and not 0 <= self.utilization_fraction <= 1:
            raise ValueError("live CPU utilization must be between zero and one")
        if self.usage_total_microseconds is not None and self.usage_total_microseconds < 0:
            raise ValueError("live CPU cumulative usage must not be negative")


@dataclass(frozen=True, slots=True)
class LiveMemoryAvailability:
    effective_limit_bytes: int
    scheduler_limit_bytes: int
    reserved_headroom_bytes: int
    current_bytes: int
    available_for_new_bytes: int
    cgroup_limit_bytes: int | None
    swap_current_bytes: int | None
    swap_limit_bytes: int | None
    scope_authoritative: bool

    def __post_init__(self) -> None:
        values = (
            self.effective_limit_bytes, self.scheduler_limit_bytes,
            self.reserved_headroom_bytes, self.current_bytes,
            self.available_for_new_bytes,
        )
        if any(value is not None and value < 0 for value in values):
            raise ValueError("live memory values must not be negative")
        if self.scheduler_limit_bytes + self.reserved_headroom_bytes > self.effective_limit_bytes:
            raise ValueError("live scheduler memory plus reserve exceeds effective limit")
        expected = (
            max(0, self.scheduler_limit_bytes - self.current_bytes)
            if self.scope_authoritative else 0
        )
        if self.available_for_new_bytes != expected:
            raise ValueError("live available memory must be derived from scheduler limit")
        optional = (self.cgroup_limit_bytes, self.swap_current_bytes, self.swap_limit_bytes)
        if any(value is not None and value < 0 for value in optional):
            raise ValueError("live optional memory values must not be negative")


@dataclass(frozen=True, slots=True)
class LiveAcceleratorAvailability:
    device_id: str
    placement_allowed: bool
    scheduler_limit_bytes: int
    current_bytes: int | None
    available_for_new_bytes: int | None
    utilization_fraction: float | None = None

    def __post_init__(self) -> None:
        _require_text(self.device_id, "accelerator device_id")
        values = (self.scheduler_limit_bytes, self.current_bytes, self.available_for_new_bytes)
        if any(value is not None and value < 0 for value in values):
            raise ValueError("live accelerator bytes must not be negative")
        if (self.current_bytes is None) != (self.available_for_new_bytes is None):
            raise ValueError("live accelerator usage and availability must be present together")
        expected = None if self.current_bytes is None else max(
            0, self.scheduler_limit_bytes - self.current_bytes
        )
        if self.available_for_new_bytes != expected:
            raise ValueError("live accelerator availability is inconsistent")
        if not self.placement_allowed and self.scheduler_limit_bytes != 0:
            raise ValueError("disallowed live accelerator must have zero scheduler limit")
        if self.utilization_fraction is not None and not 0 <= self.utilization_fraction <= 1:
            raise ValueError("accelerator utilization must be between zero and one")


@dataclass(frozen=True, slots=True)
class LiveStorageAvailability:
    storage_id: str
    scheduler_cache_limit_bytes: int
    current_cache_bytes: int | None
    available_cache_bytes: int | None

    def __post_init__(self) -> None:
        _require_text(self.storage_id, "storage_id")
        values = (
            self.scheduler_cache_limit_bytes,
            self.current_cache_bytes,
            self.available_cache_bytes,
        )
        if any(value is not None and value < 0 for value in values):
            raise ValueError("live storage cache bytes must not be negative")
        if (self.current_cache_bytes is None) != (self.available_cache_bytes is None):
            raise ValueError("live storage usage and availability must be present together")
        expected = None if self.current_cache_bytes is None else max(
            0, self.scheduler_cache_limit_bytes - self.current_cache_bytes
        )
        if self.available_cache_bytes != expected:
            raise ValueError("live storage cache availability is inconsistent")


@dataclass(frozen=True, slots=True)
class ManagedServiceUsage:
    service_id: str
    memory_current_bytes: int | None
    memory_peak_bytes: int | None
    cpu_usage_microseconds: int | None
    oom_kill_count: int | None

    def __post_init__(self) -> None:
        _require_text(self.service_id, "service_id")
        values = (
            self.memory_current_bytes, self.memory_peak_bytes,
            self.cpu_usage_microseconds, self.oom_kill_count,
        )
        if any(value is not None and value < 0 for value in values):
            raise ValueError("managed service usage must not be negative")


@dataclass(frozen=True, slots=True)
class SchedulerResourceObservation:
    observation_id: str
    sequence: int
    previous_observation_id: str | None
    observed_at: datetime
    budget_id: str
    inventory_id: str
    validation_profile_id: str
    scope_service_id: str
    status: ObservationStatus
    cpu: LiveCpuAvailability
    memory: LiveMemoryAvailability
    accelerators: tuple[LiveAcceleratorAvailability, ...]
    storage: tuple[LiveStorageAvailability, ...]
    managed_services: tuple[ManagedServiceUsage, ...]
    reason_codes: tuple[str, ...] = ()
    contract_version: str = LIVE_RESOURCE_OBSERVATION_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != LIVE_RESOURCE_OBSERVATION_VERSION:
            raise ValueError("unsupported live resource observation contract_version")
        for name in (
            "observation_id", "budget_id", "inventory_id",
            "validation_profile_id", "scope_service_id",
        ):
            _require_text(getattr(self, name), name)
        if self.sequence <= 0:
            raise ValueError("live resource sequence must be positive")
        if (self.sequence == 1) != (self.previous_observation_id is None):
            raise ValueError("live observation predecessor does not match sequence")
        if self.previous_observation_id is not None:
            _require_text(self.previous_observation_id, "previous_observation_id")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("live observation time must be timezone-aware")
        _require_unique(self.accelerators, "device_id", "accelerators")
        _require_unique(self.storage, "storage_id", "storage")
        _require_unique(self.managed_services, "service_id", "managed services")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("live observation reason codes must be unique")
        if self.status is ObservationStatus.DEGRADED and not self.reason_codes:
            raise ValueError("degraded live observation requires reason codes")
        if self.status is not ObservationStatus.DEGRADED and self.reason_codes:
            raise ValueError("non-degraded observation cannot carry reason codes")
        has_delta = self.cpu.interval_seconds is not None
        if self.status is ObservationStatus.BASELINE and (self.sequence != 1 or has_delta):
            raise ValueError("baseline must be the first observation without a CPU delta")
        if self.status is ObservationStatus.COMPLETE and not has_delta:
            raise ValueError("complete observation requires a CPU delta")


def _require_unique(values, attribute, name):
    identities = tuple(getattr(item, attribute) for item in values)
    if len(set(identities)) != len(identities):
        raise ValueError(f"live {name} must be unique")


def _require_text(value, name):
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
