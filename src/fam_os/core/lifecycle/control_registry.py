"""In-memory deadline and control replay registries."""

from dataclasses import dataclass, field
from threading import Lock

from fam_os.core.lifecycle.control_contracts import PlanDeadlinePolicy


@dataclass(frozen=True, slots=True)
class InMemoryDeadlinePolicyRegistry:
    policies: tuple[PlanDeadlinePolicy, ...]

    def get(self, plan_id: str) -> PlanDeadlinePolicy | None:
        return next((item for item in self.policies if item.plan_id == plan_id), None)


@dataclass(slots=True)
class InMemoryControlReplayRegistry:
    _ids: set[str] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock)

    def reserve(self, control_id: str) -> bool:
        with self._lock:
            if control_id in self._ids:
                return False
            self._ids.add(control_id)
            return True
