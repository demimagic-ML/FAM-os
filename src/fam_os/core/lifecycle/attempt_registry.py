"""Atomic in-memory attempt policy and replay registries."""

from dataclasses import dataclass, field
from threading import Lock

from fam_os.core.lifecycle.attempt_contracts import AttemptBudgetPolicy


@dataclass(frozen=True, slots=True)
class InMemoryAttemptPolicyRegistry:
    policies: tuple[AttemptBudgetPolicy, ...]

    def __post_init__(self) -> None:
        if len({policy.plan_id for policy in self.policies}) != len(self.policies):
            raise ValueError("attempt policies require unique plan IDs")

    def get(self, plan_id: str) -> AttemptBudgetPolicy | None:
        return next((policy for policy in self.policies if policy.plan_id == plan_id), None)


@dataclass(slots=True)
class InMemoryAttemptReplayRegistry:
    _attempt_ids: set[str] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock)

    def reserve(self, attempt_ids: tuple[str, ...]) -> bool:
        if len(set(attempt_ids)) != len(attempt_ids):
            return False
        with self._lock:
            if any(attempt_id in self._attempt_ids for attempt_id in attempt_ids):
                return False
            self._attempt_ids.update(attempt_ids)
            return True
