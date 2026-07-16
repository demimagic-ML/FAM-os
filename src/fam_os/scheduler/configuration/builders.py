"""Discovered-capacity clamps for effective scheduler resource budgets."""

from __future__ import annotations

from fam_os.scheduler.configuration.audit import (
    ConfigurationDecision,
    ConfigurationDecisionKind,
    ConfigurationLayer,
)
from fam_os.scheduler.configuration.discovery import DiscoveredResourceState
from fam_os.scheduler.configuration.policy import ResourcePolicy
from fam_os.scheduler.resources import (
    AcceleratorResourceBudget,
    CpuResourceBudget,
    MemoryResourceBudget,
    StorageResourceBudget,
)


def build_cpu_budget(
    policy: ResourcePolicy, state: DiscoveredResourceState
) -> tuple[CpuResourceBudget, ConfigurationDecision]:
    visible = tuple(sorted(state.inventory.cpu.logical_cpu_ids))
    reserve_count = policy.reserved_logical_cpu_count
    if reserve_count >= len(visible):
        raise ValueError("CPU reserve must leave at least one schedulable logical CPU")
    reserved = visible[-reserve_count:] if reserve_count else ()
    schedulable = visible[:-reserve_count] if reserve_count else visible
    requested = len(visible) * policy.cpu_quota_fraction
    if policy.max_cpu_cores is not None:
        requested = min(requested, policy.max_cpu_cores)
    effective = min(requested, float(len(schedulable)))
    if state.cgroup_cpu_quota_cores is not None:
        effective = min(effective, state.cgroup_cpu_quota_cores)
    budget = CpuResourceBudget(
        visible,
        schedulable,
        reserved,
        effective,
        _pressure_utilization(state, "cpu"),
        state.cgroup_cpu_quota_cores,
    )
    return budget, _clamp("cpu_quota_cores", requested, effective, state.state_id)


def build_memory_budget(
    policy: ResourcePolicy, state: DiscoveredResourceState
) -> tuple[MemoryResourceBudget, tuple[ConfigurationDecision, ...]]:
    host_limit = state.inventory.memory.total_bytes
    effective_limit = host_limit
    if state.cgroup_memory_limit_bytes is not None:
        effective_limit = min(effective_limit, state.cgroup_memory_limit_bytes)
    headroom = policy.memory_headroom_bytes
    if headroom >= effective_limit:
        raise ValueError("memory headroom must leave a positive scheduler limit")
    requested = int(effective_limit * policy.memory_limit_fraction)
    if policy.max_memory_bytes is not None:
        requested = min(requested, policy.max_memory_bytes)
    scheduler_limit = min(requested, effective_limit - headroom)
    swap_limit = min(policy.max_swap_bytes, state.swap_limit_bytes)
    budget = MemoryResourceBudget(
        effective_limit,
        scheduler_limit,
        headroom,
        state.memory_current_bytes,
        swap_limit,
        state.swap_current_bytes,
        state.cgroup_memory_limit_bytes,
    )
    return budget, (
        _clamp("memory_limit_bytes", requested, scheduler_limit, state.state_id),
        _clamp("swap_limit_bytes", policy.max_swap_bytes, swap_limit, state.state_id),
    )


def build_accelerator_budgets(
    policy: ResourcePolicy, state: DiscoveredResourceState
) -> tuple[tuple[AcceleratorResourceBudget, ...], tuple[ConfigurationDecision, ...]]:
    current = {item.device_id: item.current_memory_bytes for item in state.accelerators}
    budgets: list[AcceleratorResourceBudget] = []
    decisions: list[ConfigurationDecision] = []
    for inventory in state.inventory.accelerators:
        effective = inventory.memory_total_bytes or 0
        reserve = min(policy.accelerator_reserved_memory_bytes, effective)
        requested = int(effective * policy.accelerator_memory_fraction)
        if policy.max_accelerator_memory_bytes is not None:
            requested = min(requested, policy.max_accelerator_memory_bytes)
        scheduler_limit = min(requested, max(0, effective - reserve))
        allowed = policy.accelerator_allowed and scheduler_limit > 0
        if not allowed:
            scheduler_limit = 0
        budgets.append(
            AcceleratorResourceBudget(
                inventory.device_id,
                allowed,
                effective,
                scheduler_limit,
                reserve,
                current.get(inventory.device_id, 0),
            )
        )
        decisions.append(
            _clamp(
                f"accelerator.{inventory.device_id}.memory_limit_bytes",
                requested,
                scheduler_limit,
                state.state_id,
            )
        )
    return tuple(budgets), tuple(decisions)


def build_storage_budgets(
    policy: ResourcePolicy, state: DiscoveredResourceState
) -> tuple[tuple[StorageResourceBudget, ...], tuple[ConfigurationDecision, ...]]:
    current = {item.storage_id: item.current_cache_bytes for item in state.storage}
    budgets: list[StorageResourceBudget] = []
    decisions: list[ConfigurationDecision] = []
    for inventory in state.inventory.storage:
        effective = inventory.available_bytes
        reserve = min(policy.storage_reserved_free_bytes, effective)
        requested = int(effective * policy.storage_cache_fraction)
        if policy.max_storage_cache_bytes is not None:
            requested = min(requested, policy.max_storage_cache_bytes)
        scheduler_limit = min(requested, max(0, effective - reserve))
        if not inventory.cache_eligible:
            scheduler_limit = 0
        budgets.append(
            StorageResourceBudget(
                inventory.storage_id,
                effective,
                scheduler_limit,
                reserve,
                current.get(inventory.storage_id, 0),
                policy.storage_read_limit_bytes_per_second,
                policy.storage_write_limit_bytes_per_second,
            )
        )
        decisions.append(
            _clamp(
                f"storage.{inventory.storage_id}.cache_limit_bytes",
                requested,
                scheduler_limit,
                state.state_id,
            )
        )
    return tuple(budgets), tuple(decisions)


def _pressure_utilization(state: DiscoveredResourceState, resource_id: str) -> float:
    reading = next((item for item in state.pressure if item.resource_id == resource_id), None)
    if reading is None or reading.utilization_fraction is None:
        return 0.0
    return reading.utilization_fraction


def _clamp(
    setting: str, requested: int | float, effective: int | float, source_id: str
) -> ConfigurationDecision:
    kind = ConfigurationDecisionKind.CLAMPED if effective < requested else ConfigurationDecisionKind.SELECTED
    return ConfigurationDecision(
        ConfigurationLayer.DISCOVERY,
        source_id,
        setting,
        str(requested),
        str(effective),
        kind,
        "discovered_capacity_ceiling" if kind is ConfigurationDecisionKind.CLAMPED else "within_discovered_capacity",
    )
