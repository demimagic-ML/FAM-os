"""Resource limits chosen before expert activation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    memory_limit_bytes: int
    swap_limit_bytes: int
    context_tokens: int
    gpu_allowed: bool = False
    npu_allowed: bool = False

    def __post_init__(self) -> None:
        if self.memory_limit_bytes <= 0:
            raise ValueError("memory_limit_bytes must be positive")
        if self.swap_limit_bytes < 0:
            raise ValueError("swap_limit_bytes cannot be negative")
        if self.context_tokens <= 0:
            raise ValueError("context_tokens must be positive")


@dataclass(frozen=True, slots=True)
class PlacementPlan:
    expert_id: str
    budget: ResourceBudget
    evict_expert_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.expert_id.strip():
            raise ValueError("expert_id must not be empty")
        if any(not expert_id.strip() for expert_id in self.evict_expert_ids):
            raise ValueError("evicted expert IDs must not be empty")
        if len(set(self.evict_expert_ids)) != len(self.evict_expert_ids):
            raise ValueError("evicted expert IDs must be unique")
        if self.expert_id in self.evict_expert_ids:
            raise ValueError("placement cannot evict the expert being activated")
