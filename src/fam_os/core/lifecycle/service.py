"""Deterministic executor for immutable execution-plan transitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fam_os.core.contracts import ExecutionPlan, StepOutcome
from fam_os.core.lifecycle.contracts import (
    PlanAdvanceResult,
    PlanAuthorityBinding,
    PlanEventKind,
    PlanEvidenceReference,
    PlanInstanceSnapshot,
    PlanLifecycleEvent,
    PlanRejection,
    PlanStartResult,
)
from fam_os.core.lifecycle.ports import PlanStateRepository
from fam_os.core.routing import RoutedTaskRequest


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier() -> str:
    return str(uuid4())


@dataclass(slots=True)
class PlanLifecycleService:
    repository: PlanStateRepository
    clock: Callable[[], datetime] = _utc_now
    instance_id_factory: Callable[[], str] = _identifier
    event_id_factory: Callable[[], str] = _identifier

    def start(self, routed: RoutedTaskRequest, plan: ExecutionPlan) -> PlanStartResult:
        if not _binding_matches(routed, plan):
            return PlanStartResult(routed.request_id, rejection=PlanRejection.INVALID_BINDING)
        instance_id = self.instance_id_factory()
        entry = _step(plan, plan.entry_step_id)
        event = PlanLifecycleEvent(
            self.event_id_factory(), 0, self.clock(), PlanEventKind.STARTED,
            plan.entry_step_id, terminal_disposition=entry.terminal_disposition,
        )
        snapshot = PlanInstanceSnapshot(
            instance_id, plan, plan.entry_step_id, 0, (event,),
            entry.terminal_disposition,
            PlanAuthorityBinding(
                routed.admitted.admission_id, routed.admitted.permission.valid_until
            ),
        )
        if not self.repository.create(snapshot):
            return PlanStartResult(routed.request_id, rejection=PlanRejection.ALREADY_STARTED)
        return PlanStartResult(routed.request_id, snapshot=snapshot)

    def advance(
        self, instance_id: str, expected_revision: int, outcome: StepOutcome,
        evidence_refs: tuple[PlanEvidenceReference, ...] = (),
    ) -> PlanAdvanceResult:
        current = self.repository.get(instance_id)
        rejection = _precondition(current, expected_revision, outcome)
        if rejection is not None:
            return PlanAdvanceResult(instance_id, rejection=rejection)
        transition = _select(current.plan, current.current_step_id, outcome)
        if transition is None:
            return PlanAdvanceResult(instance_id, rejection=PlanRejection.ILLEGAL_OUTCOME)
        try:
            updated = self._updated(
                current, transition.target_step_id, outcome, evidence_refs
            )
        except ValueError:
            return PlanAdvanceResult(instance_id, rejection=PlanRejection.ILLEGAL_OUTCOME)
        if not self.repository.replace(expected_revision, updated):
            return PlanAdvanceResult(instance_id, rejection=PlanRejection.REVISION_CONFLICT)
        return PlanAdvanceResult(instance_id, snapshot=updated)

    def _updated(self, current, target_step_id, outcome, evidence_refs) -> PlanInstanceSnapshot:
        revision = current.revision + 1
        target = _step(current.plan, target_step_id)
        event = PlanLifecycleEvent(
            self.event_id_factory(), revision, self.clock(),
            PlanEventKind.TRANSITIONED, target_step_id,
            current.current_step_id, outcome, target.terminal_disposition, evidence_refs,
        )
        return PlanInstanceSnapshot(
            current.instance_id, current.plan, target_step_id, revision,
            current.events + (event,), target.terminal_disposition,
            current.authority_binding,
        )


def _binding_matches(routed: RoutedTaskRequest, plan: ExecutionPlan) -> bool:
    decision = routed.routing.decision
    effective = routed.admitted.permission.authorized_capabilities
    return (
        plan.request_id == routed.request_id
        and plan.route == decision
        and plan.route.required_capabilities == effective
    )


def _precondition(current, expected_revision, outcome) -> PlanRejection | None:
    if current is None:
        return PlanRejection.NOT_FOUND
    if expected_revision != current.revision:
        return PlanRejection.REVISION_CONFLICT
    if current.terminal:
        return PlanRejection.TERMINAL
    if not isinstance(outcome, StepOutcome):
        return PlanRejection.ILLEGAL_OUTCOME
    return None


def _select(plan, source_step_id, outcome):
    for transition in plan.transitions:
        if transition.source_step_id == source_step_id and transition.outcome is outcome:
            return transition
    return None


def _step(plan, step_id):
    return next(step for step in plan.steps if step.step_id == step_id)
