"""Top-level deterministic configuration-layer composition use case."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.scheduler.configuration.audit import ConfigurationDecision
from fam_os.scheduler.configuration.builders import (
    build_accelerator_budgets,
    build_cpu_budget,
    build_memory_budget,
    build_storage_budgets,
)
from fam_os.scheduler.configuration.discovery import DiscoveredResourceState
from fam_os.scheduler.configuration.layering import resolve_policy
from fam_os.scheduler.configuration.policy import (
    CONFIGURATION_CONTRACT_VERSION,
    SchedulerDefaults,
    SessionResourceOverride,
    UserResourcePolicy,
    ValidationProfileConfiguration,
)
from fam_os.scheduler.resources import EffectiveResourceBudget


@dataclass(frozen=True, slots=True)
class ConfigurationCompositionRequest:
    composition_id: str
    defaults: SchedulerDefaults
    discovery: DiscoveredResourceState
    profile: ValidationProfileConfiguration | None = None
    user_policy: UserResourcePolicy | None = None
    session_override: SessionResourceOverride | None = None
    contract_version: str = CONFIGURATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.composition_id.strip():
            raise ValueError("composition_id must not be empty")
        if self.contract_version != CONFIGURATION_CONTRACT_VERSION:
            raise ValueError("unsupported composition request contract_version")


@dataclass(frozen=True, slots=True)
class ComposedResourceConfiguration:
    composition_id: str
    budget: EffectiveResourceBudget
    decisions: tuple[ConfigurationDecision, ...]
    contract_version: str = CONFIGURATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.composition_id.strip() or not self.decisions:
            raise ValueError("composed configuration requires identity and decisions")
        if self.contract_version != CONFIGURATION_CONTRACT_VERSION:
            raise ValueError("unsupported composed configuration contract_version")
        if self.composition_id != self.budget.budget_id:
            raise ValueError("composition and budget identity must match")


def compose_resource_configuration(
    request: ConfigurationCompositionRequest,
) -> ComposedResourceConfiguration:
    profile, policy, layer_decisions = resolve_policy(
        request.defaults,
        request.profile,
        request.user_policy,
        request.session_override,
        request.discovery.captured_at,
    )
    cpu, cpu_decision = build_cpu_budget(policy, request.discovery)
    memory, memory_decisions = build_memory_budget(policy, request.discovery)
    accelerators, accelerator_decisions = build_accelerator_budgets(policy, request.discovery)
    storage, storage_decisions = build_storage_budgets(policy, request.discovery)
    budget = EffectiveResourceBudget(
        request.composition_id,
        request.discovery.inventory.inventory_id,
        request.discovery.captured_at,
        profile,
        cpu,
        memory,
        accelerators,
        storage,
        request.discovery.pressure,
    )
    decisions = (
        *layer_decisions,
        cpu_decision,
        *memory_decisions,
        *accelerator_decisions,
        *storage_decisions,
    )
    return ComposedResourceConfiguration(request.composition_id, budget, decisions)
