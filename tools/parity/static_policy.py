"""Explicit in-memory catalog and placement policy for parity measurements."""

from __future__ import annotations

from fam_os.experts.contracts import ExpertDescriptor
from fam_os.scheduler.contracts import PlacementPlan


class StaticExpertCatalog:
    def __init__(self, experts: tuple[ExpertDescriptor, ...]) -> None:
        self._experts = {expert.expert_id: expert for expert in experts}
        if len(self._experts) != len(experts):
            raise ValueError("expert IDs must be unique")

    def get(self, expert_id: str) -> ExpertDescriptor | None:
        return self._experts.get(expert_id)


class StaticPlacementPlanner:
    def __init__(self, plans: tuple[PlacementPlan, ...]) -> None:
        self._plans = {plan.expert_id: plan for plan in plans}
        if len(self._plans) != len(plans):
            raise ValueError("placement expert IDs must be unique")

    def plan(self, expert: ExpertDescriptor) -> PlacementPlan:
        try:
            return self._plans[expert.expert_id]
        except KeyError as error:
            raise ValueError(f"no placement for expert: {expert.expert_id}") from error
