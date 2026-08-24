"""Profile-derived cgroup limits for production worker classes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.scheduler.resources import EffectiveResourceBudget
from fam_os.supervisor import ResourceLimits


WORKER_BUDGET_VERSION = "fam.product.worker-budget/v1alpha1"


class WorkerKind(StrEnum):
    MODEL = "model"
    VERIFIER = "verifier"
    CONNECTOR = "connector"
    TRAINING = "training"


@dataclass(frozen=True, slots=True)
class WorkerBudgetShare:
    worker_kind: WorkerKind
    memory_fraction: float
    memory_high_fraction: float
    cpu_fraction: float
    tasks_max: int

    def __post_init__(self) -> None:
        if not 0 < self.memory_fraction <= 1 or not 0 < self.cpu_fraction <= 1:
            raise ValueError("worker memory and CPU fractions must be in (0, 1]")
        if not 0 < self.memory_high_fraction <= 1 or self.tasks_max <= 0:
            raise ValueError("worker high-memory fraction and task limit are invalid")


@dataclass(frozen=True, slots=True)
class WorkerBudgetPolicy:
    policy_id: str
    shares: tuple[WorkerBudgetShare, ...]
    contract_version: str = WORKER_BUDGET_VERSION

    def __post_init__(self) -> None:
        kinds = tuple(item.worker_kind for item in self.shares)
        if not self.policy_id.strip() or set(kinds) != set(WorkerKind):
            raise ValueError("worker budget policy must define every worker kind")
        if len(set(kinds)) != len(kinds) or self.contract_version != WORKER_BUDGET_VERSION:
            raise ValueError("worker budget policy is invalid")


@dataclass(frozen=True, slots=True)
class WorkerLimitPlan:
    budget_id: str
    worker_kind: WorkerKind
    limits: ResourceLimits
    contract_version: str = WORKER_BUDGET_VERSION


def derive_worker_limits(
    budget: EffectiveResourceBudget,
    policy: WorkerBudgetPolicy,
) -> tuple[WorkerLimitPlan, ...]:
    return tuple(_derive(budget, share) for share in policy.shares)


def _derive(budget: EffectiveResourceBudget, share: WorkerBudgetShare) -> WorkerLimitPlan:
    maximum = max(1, int(budget.memory.scheduler_limit_bytes * share.memory_fraction))
    high = max(1, int(maximum * share.memory_high_fraction))
    cpu = max(1.0, budget.cpu.scheduler_quota_cores * share.cpu_fraction) * 100
    return WorkerLimitPlan(
        budget.budget_id,
        share.worker_kind,
        ResourceLimits(
            memory_max_bytes=maximum,
            swap_max_bytes=budget.memory.swap_limit_bytes,
            cpu_quota_percent=cpu,
            tasks_max=share.tasks_max,
            memory_high_bytes=high,
        ),
    )
