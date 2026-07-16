"""Port for deterministic expert placement and eviction policy."""

from typing import Protocol

from fam_os.experts.contracts import ExpertDescriptor
from fam_os.scheduler.contracts import PlacementPlan


class PlacementPlanner(Protocol):
    def plan(self, expert: ExpertDescriptor) -> PlacementPlan: ...
