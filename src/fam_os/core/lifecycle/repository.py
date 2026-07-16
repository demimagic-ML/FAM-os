"""Atomic in-memory persistence for plan lifecycle snapshots."""

from dataclasses import dataclass, field
from threading import Lock

from fam_os.core.lifecycle.contracts import PlanInstanceSnapshot


@dataclass(slots=True)
class InMemoryPlanStateRepository:
    _instances: dict[str, PlanInstanceSnapshot] = field(default_factory=dict)
    _bindings: set[tuple[str, str]] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock)

    def create(self, snapshot: PlanInstanceSnapshot) -> bool:
        binding = (snapshot.plan.request_id, snapshot.plan.plan_id)
        with self._lock:
            if snapshot.instance_id in self._instances or binding in self._bindings:
                return False
            self._instances[snapshot.instance_id] = snapshot
            self._bindings.add(binding)
            return True

    def get(self, instance_id: str) -> PlanInstanceSnapshot | None:
        with self._lock:
            return self._instances.get(instance_id)

    def replace(self, expected_revision: int, snapshot: PlanInstanceSnapshot) -> bool:
        with self._lock:
            current = self._instances.get(snapshot.instance_id)
            if current is None or current.revision != expected_revision:
                return False
            if snapshot.revision != expected_revision + 1:
                return False
            if snapshot.plan != current.plan:
                return False
            if snapshot.authority_binding != current.authority_binding:
                return False
            self._instances[snapshot.instance_id] = snapshot
            return True
