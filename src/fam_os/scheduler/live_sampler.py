"""Repeated cgroup-aware scheduler resource sampling."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from fam_os.scheduler.live_contracts import (
    LiveAcceleratorAvailability,
    LiveCpuAvailability,
    LiveMemoryAvailability,
    LiveStorageAvailability,
    ManagedServiceUsage,
    ObservationStatus,
    SchedulerResourceObservation,
)
from fam_os.scheduler.live_ports import AcceleratorRuntimeObserver, StorageRuntimeObserver
from fam_os.scheduler.resources import EffectiveResourceBudget
from fam_os.supervisor import ResourceObserver


@dataclass(frozen=True, slots=True)
class LiveResourceSampler:
    budget: EffectiveResourceBudget
    resource_observer: ResourceObserver
    accelerator_observer: AcceleratorRuntimeObserver
    storage_observer: StorageRuntimeObserver
    scope_service_id: str
    managed_service_ids: tuple[str, ...]
    clock: Callable[[], datetime]
    observation_id_factory: Callable[[], str]

    def __post_init__(self) -> None:
        if not self.scope_service_id.strip():
            raise ValueError("scope_service_id must not be empty")
        if len(set(self.managed_service_ids)) != len(self.managed_service_ids):
            raise ValueError("managed service IDs must be unique")
        if any(not service_id.strip() for service_id in self.managed_service_ids):
            raise ValueError("managed service IDs must not be empty")

    def sample(
        self, previous: SchedulerResourceObservation | None = None
    ) -> SchedulerResourceObservation:
        observed_at = self.clock()
        _validate_previous(self.budget, self.scope_service_id, previous, observed_at)
        scope = self.resource_observer.observe(self.scope_service_id)
        children = tuple(
            self.resource_observer.observe(service_id)
            for service_id in self.managed_service_ids
        )
        reasons: list[str] = []
        if scope is None:
            reasons.append("cgroup.scope_unavailable")
        managed = _managed_usage(self.managed_service_ids, children, reasons)
        cpu = _cpu_availability(self.budget, scope, previous, observed_at, reasons)
        memory = _memory_availability(self.budget, scope, children, reasons)
        accelerators = _accelerator_availability(
            self.budget, self.accelerator_observer.observe_accelerators(), reasons
        )
        storage = _storage_availability(
            self.budget, self.storage_observer.observe_storage(), reasons
        )
        sequence = 1 if previous is None else previous.sequence + 1
        status = _status(sequence, cpu, reasons)
        return SchedulerResourceObservation(
            observation_id=self.observation_id_factory(),
            sequence=sequence,
            previous_observation_id=None if previous is None else previous.observation_id,
            observed_at=observed_at,
            budget_id=self.budget.budget_id,
            inventory_id=self.budget.inventory_id,
            validation_profile_id=self.budget.validation_profile.profile_id,
            scope_service_id=self.scope_service_id,
            status=status,
            cpu=cpu,
            memory=memory,
            accelerators=accelerators,
            storage=storage,
            managed_services=managed,
            reason_codes=tuple(dict.fromkeys(reasons)),
        )


def _validate_previous(budget, scope_id, previous, observed_at):
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("live sampler clock must return a timezone-aware time")
    if previous is None:
        return
    identity = (previous.budget_id, previous.inventory_id, previous.scope_service_id)
    expected = (budget.budget_id, budget.inventory_id, scope_id)
    if identity != expected:
        raise ValueError("previous live observation belongs to another resource scope")
    if observed_at <= previous.observed_at:
        raise ValueError("live observation time must increase")


def _managed_usage(service_ids, snapshots, reasons):
    result = []
    for service_id, snapshot in zip(service_ids, snapshots, strict=True):
        if snapshot is None:
            reasons.append(f"cgroup.managed_unavailable:{service_id}")
        result.append(
            ManagedServiceUsage(
                service_id=service_id,
                memory_current_bytes=_value(snapshot, "memory_current_bytes"),
                memory_peak_bytes=_value(snapshot, "memory_peak_bytes"),
                cpu_usage_microseconds=_value(snapshot, "cpu_usage_microseconds"),
                oom_kill_count=None if snapshot is None else snapshot.event_count("oom_kill"),
            )
        )
    return tuple(result)


def _cpu_availability(budget, scope, previous, observed_at, reasons):
    cgroup_quota = _cgroup_cpu_quota(scope)
    quota = budget.cpu.scheduler_quota_cores
    if cgroup_quota is not None:
        quota = min(quota, cgroup_quota)
    current = _value(scope, "cpu_usage_microseconds")
    prior = None if previous is None else previous.cpu
    if current is None:
        reasons.append("cgroup.cpu_usage_unavailable")
    if prior is None or prior.usage_total_microseconds is None or current is None:
        return LiveCpuAvailability(quota, cgroup_quota, None, None, None, current)
    interval = (observed_at - previous.observed_at).total_seconds()
    if current < prior.usage_total_microseconds:
        reasons.append("cgroup.cpu_counter_reset")
        return LiveCpuAvailability(quota, cgroup_quota, None, None, None, current)
    delta = current - prior.usage_total_microseconds
    utilization = min(1.0, delta / (interval * 1_000_000 * quota))
    return LiveCpuAvailability(quota, cgroup_quota, interval, delta, utilization, current)


def _memory_availability(budget, scope, children, reasons):
    cgroup_limit = _ceiling_bytes(_value(scope, "memory_limit"))
    effective = min(
        budget.memory.effective_limit_bytes,
        budget.memory.effective_limit_bytes if cgroup_limit is None else cgroup_limit,
    )
    reserve = min(budget.memory.reserved_headroom_bytes, effective)
    scheduler = min(budget.memory.scheduler_limit_bytes, max(0, effective - reserve))
    current = _value(scope, "memory_current_bytes")
    if current is None:
        known = [item.memory_current_bytes for item in children if item is not None]
        current = sum(value for value in known if value is not None)
        reasons.append("cgroup.scope_memory_fallback")
    authoritative = scope is not None and scope.memory_current_bytes is not None
    return LiveMemoryAvailability(
        effective, scheduler, reserve, current,
        max(0, scheduler - current) if authoritative else 0,
        cgroup_limit, _value(scope, "swap_current_bytes"),
        _ceiling_bytes(_value(scope, "swap_limit")), authoritative,
    )


def _accelerator_availability(budget, runtime, reasons):
    observed = {item.device_id: item for item in runtime}
    result = []
    for item in budget.accelerators:
        state = observed.get(item.device_id)
        if state is None and item.placement_allowed:
            reasons.append(f"accelerator.unavailable:{item.device_id}")
        current = None if state is None else state.current_memory_bytes
        limit = item.scheduler_memory_limit_bytes
        result.append(LiveAcceleratorAvailability(
            item.device_id, item.placement_allowed, limit, current,
            None if current is None else max(0, limit - current),
            None if state is None else state.utilization_fraction,
        ))
    return tuple(result)


def _storage_availability(budget, runtime, reasons):
    observed = {item.storage_id: item for item in runtime}
    result = []
    for item in budget.storage:
        state = observed.get(item.storage_id)
        if state is None:
            reasons.append(f"storage.unavailable:{item.storage_id}")
        current = None if state is None else state.current_cache_bytes
        limit = item.scheduler_cache_limit_bytes
        result.append(LiveStorageAvailability(
            item.storage_id, limit, current,
            None if current is None else max(0, limit - current)
        ))
    return tuple(result)


def _status(sequence, cpu, reasons):
    if reasons:
        return ObservationStatus.DEGRADED
    if sequence == 1 or cpu.interval_seconds is None:
        return ObservationStatus.BASELINE
    return ObservationStatus.COMPLETE


def _cgroup_cpu_quota(snapshot):
    ceiling = _value(snapshot, "cpu_quota")
    if ceiling is None or ceiling.maximum_percent is None:
        return None
    return ceiling.maximum_percent / 100.0


def _ceiling_bytes(ceiling):
    return None if ceiling is None else ceiling.maximum_bytes


def _value(instance, attribute):
    return None if instance is None else getattr(instance, attribute)
