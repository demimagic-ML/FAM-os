"""Shared profile and effective-budget admission for every parity workload."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fam_os.scheduler import (
    EffectiveResourceBudget,
    ResourceBudget,
    ValidationProfileDocument,
)
from fam_os.schemas import loads_document


GIBIBYTE = 1024**3


@dataclass(frozen=True, slots=True)
class BenchmarkComposition:
    profile: ValidationProfileDocument
    budget: EffectiveResourceBudget
    profile_path: Path | None = None
    budget_path: Path | None = None

    def __post_init__(self) -> None:
        if self.profile.configuration.profile != self.budget.validation_profile:
            raise ValueError("benchmark profile and effective budget must identify the same profile")
        service = self.profile.service
        if service.memory_max_bytes is not None:
            committed = (
                self.budget.memory.scheduler_limit_bytes
                + self.budget.memory.reserved_headroom_bytes
            )
            if committed > service.memory_max_bytes:
                raise ValueError("scheduler memory plus reserve exceeds the profile service envelope")
        if self.budget.memory.swap_limit_bytes > service.swap_max_bytes:
            raise ValueError("effective swap exceeds the profile service envelope")
        if service.cpu_quota_cores is not None:
            if self.budget.cpu.scheduler_quota_cores > service.cpu_quota_cores:
                raise ValueError("effective CPU quota exceeds the profile service envelope")
        if service.accelerator_visibility.value == "deny_all":
            if any(item.placement_allowed for item in self.budget.accelerators):
                raise ValueError("hidden accelerators cannot have placement authority")

    def placement_budget(self, context_tokens: int) -> ResourceBudget:
        return ResourceBudget(
            self.budget.memory.scheduler_limit_bytes,
            self.budget.memory.swap_limit_bytes,
            context_tokens,
            gpu_allowed=any(item.placement_allowed for item in self.budget.accelerators),
        )

    def constraints_payload(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile.profile_id,
            "profile_document_id": self.profile.document_id,
            "effective_budget_id": self.budget.budget_id,
            "service_memory_max_bytes": self.profile.service.memory_max_bytes,
            "service_swap_max_bytes": self.profile.service.swap_max_bytes,
            "accelerator_visibility": self.profile.service.accelerator_visibility.value,
            "memory_effective_limit_bytes": self.budget.memory.effective_limit_bytes,
            "memory_scheduler_limit_bytes": self.budget.memory.scheduler_limit_bytes,
            "memory_headroom_bytes": self.budget.memory.reserved_headroom_bytes,
            "swap_limit_bytes": self.budget.memory.swap_limit_bytes,
            "cpu_scheduler_quota_cores": self.budget.cpu.scheduler_quota_cores,
            "gpu_allowed": any(item.placement_allowed for item in self.budget.accelerators),
            "accelerator_budgets": [
                {
                    "device_id": item.device_id,
                    "placement_allowed": item.placement_allowed,
                    "scheduler_memory_limit_bytes": item.scheduler_memory_limit_bytes,
                    "reserved_memory_bytes": item.reserved_memory_bytes,
                }
                for item in self.budget.accelerators
            ],
            "storage_budgets": [
                {
                    "storage_id": item.storage_id,
                    "scheduler_cache_limit_bytes": item.scheduler_cache_limit_bytes,
                    "reserved_free_bytes": item.reserved_free_bytes,
                }
                for item in self.budget.storage
            ],
        }


def load_benchmark_composition(
    profile_path: Path, budget_path: Path
) -> BenchmarkComposition:
    profile = loads_document(profile_path.read_text(encoding="utf-8"))
    budget = loads_document(budget_path.read_text(encoding="utf-8"))
    if not isinstance(profile, ValidationProfileDocument):
        raise TypeError("profile path does not contain a validation profile document")
    if not isinstance(budget, EffectiveResourceBudget):
        raise TypeError("budget path does not contain an effective resource budget")
    return BenchmarkComposition(profile, budget, profile_path.resolve(), budget_path.resolve())
