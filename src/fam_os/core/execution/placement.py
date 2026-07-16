"""Execution of scheduler-selected evictions before expert activation."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.core.ports.inference import InferenceRuntime
from fam_os.experts.contracts import ExpertDescriptor
from fam_os.experts.ports import ExpertCatalog
from fam_os.scheduler.contracts import PlacementPlan
from fam_os.scheduler.ports.placement import PlacementPlanner


@dataclass(frozen=True, slots=True)
class PreparedPlacement:
    plan: PlacementPlan
    evicted_expert_ids: tuple[str, ...]


class PlacementExecutionError(RuntimeError):
    """Raised when a scheduler plan cannot be executed safely."""


class PlacementExecutor:
    def __init__(
        self,
        runtime: InferenceRuntime,
        catalog: ExpertCatalog,
        planner: PlacementPlanner,
    ) -> None:
        self._runtime = runtime
        self._catalog = catalog
        self._planner = planner

    def prepare(self, expert: ExpertDescriptor) -> PreparedPlacement:
        plan = self._planner.plan(expert)
        if plan.expert_id != expert.expert_id:
            raise PlacementExecutionError("placement plan targets a different expert")
        evictions = self._resolve_evictions(plan)
        for evicted in evictions:
            self._runtime.unload(evicted.model_ref)
        return PreparedPlacement(plan, tuple(item.expert_id for item in evictions))

    def _resolve_evictions(self, plan: PlacementPlan) -> tuple[ExpertDescriptor, ...]:
        resolved: list[ExpertDescriptor] = []
        for expert_id in plan.evict_expert_ids:
            expert = self._catalog.get(expert_id)
            if expert is None:
                raise PlacementExecutionError(
                    f"placement references unknown expert: {expert_id}"
                )
            resolved.append(expert)
        return tuple(resolved)
