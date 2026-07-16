"""Persistence port for generic Core plan lifecycle state."""

from typing import Protocol

from fam_os.core.lifecycle.contracts import PlanInstanceSnapshot


class PlanStateRepository(Protocol):
    def create(self, snapshot: PlanInstanceSnapshot) -> bool: ...

    def get(self, instance_id: str) -> PlanInstanceSnapshot | None: ...

    def replace(self, expected_revision: int, snapshot: PlanInstanceSnapshot) -> bool: ...
