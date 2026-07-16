"""Replay-safe cancellation, timeout, and degradation transitions."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from fam_os.core.contracts import DegradationNotice, StepOutcome
from fam_os.core.lifecycle.control_contracts import (
    ControlCommand, ControlKind, ControlRejection, ControlTransitionResult,
)
from fam_os.core.lifecycle.control_ports import ControlReplayRegistry, DeadlinePolicyRegistry
from fam_os.core.lifecycle.contracts import (
    PlanEvidenceKind, PlanEvidenceReference, PlanRejection,
)
from fam_os.core.lifecycle.service import PlanLifecycleService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class PlanControlService:
    lifecycle: PlanLifecycleService
    deadlines: DeadlinePolicyRegistry
    replay: ControlReplayRegistry
    clock: Callable[[], datetime] = _utc_now

    def cancel(self, command: ControlCommand) -> ControlTransitionResult:
        return self._transition(
            command, StepOutcome.CANCELLED, ControlKind.CANCELLED,
            PlanEvidenceKind.CANCELLATION,
        )

    def timeout(self, command: ControlCommand) -> ControlTransitionResult:
        snapshot, rejection = self._context(command)
        if rejection is not None:
            return _rejected(command.plan_instance_id, rejection)
        policy = self.deadlines.get(snapshot.plan.plan_id)
        if policy is None or self.clock() < policy.deadline:
            return _rejected(command.plan_instance_id, ControlRejection.NOT_DUE)
        return self._transition(
            command, StepOutcome.UNAVAILABLE, ControlKind.TIMED_OUT,
            PlanEvidenceKind.TIMEOUT,
        )

    def degrade(self, command: ControlCommand) -> ControlTransitionResult:
        if not isinstance(command.degradation, DegradationNotice):
            return _rejected(command.plan_instance_id, ControlRejection.INVALID_CONTEXT)
        if command.control_id != command.degradation.degradation_id:
            return _rejected(command.plan_instance_id, ControlRejection.INVALID_CONTEXT)
        return self._transition(
            command, StepOutcome.UNAVAILABLE, ControlKind.DEGRADED,
            PlanEvidenceKind.DEGRADATION, command.degradation,
        )

    def _transition(self, command, outcome, kind, evidence_kind, degradation=None):
        snapshot, rejection = self._context(command)
        if rejection is not None:
            return _rejected(command.plan_instance_id, rejection)
        if not _has_transition(snapshot, outcome):
            return _rejected(command.plan_instance_id, PlanRejection.ILLEGAL_OUTCOME)
        if not self.replay.reserve(command.control_id):
            return _rejected(command.plan_instance_id, ControlRejection.REPLAYED)
        capability = snapshot.plan.route.required_capabilities[0] \
            if snapshot.plan.route.required_capabilities else None
        reference_id = degradation.degradation_id if degradation else command.control_id
        reference = PlanEvidenceReference(reference_id, evidence_kind, capability)
        advanced = self.lifecycle.advance(
            command.plan_instance_id, command.expected_revision, outcome, (reference,)
        )
        if advanced.rejection is not None:
            return _rejected(command.plan_instance_id, advanced.rejection)
        return ControlTransitionResult(
            command.plan_instance_id, kind, advanced.snapshot, degradation
        )

    def _context(self, command):
        snapshot = self.lifecycle.repository.get(command.plan_instance_id)
        rejection = _snapshot_rejection(snapshot, command.expected_revision)
        if rejection is not None:
            return None, rejection
        if not _route_context_matches(snapshot, command.routed):
            return None, ControlRejection.INVALID_CONTEXT
        return snapshot, None


def _snapshot_rejection(snapshot, revision):
    if snapshot is None:
        return PlanRejection.NOT_FOUND
    if snapshot.revision != revision:
        return PlanRejection.REVISION_CONFLICT
    if snapshot.terminal:
        return PlanRejection.TERMINAL
    return None


def _route_context_matches(snapshot, routed) -> bool:
    return (
        snapshot.plan.request_id == routed.request_id
        and snapshot.plan.route == routed.routing.decision
        and snapshot.authority_binding.admission_id == routed.admitted.admission_id
        and snapshot.authority_binding.valid_until == routed.admitted.permission.valid_until
    )


def _has_transition(snapshot, outcome) -> bool:
    return any(
        item.source_step_id == snapshot.current_step_id and item.outcome is outcome
        for item in snapshot.plan.transitions
    )


def _rejected(instance_id, rejection):
    return ControlTransitionResult(instance_id, rejection=rejection)
