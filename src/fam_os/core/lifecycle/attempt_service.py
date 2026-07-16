"""Budgeted transitions into unrolled repair and escalation steps."""

from dataclasses import dataclass

from fam_os.core.contracts import PlanStepKind, StepOutcome
from fam_os.core.lifecycle.attempt_contracts import (
    AttemptKind,
    AttemptRejection,
    AttemptTransitionCommand,
    AttemptTransitionResult,
)
from fam_os.core.lifecycle.attempt_ports import AttemptPolicyRegistry, AttemptReplayRegistry
from fam_os.core.lifecycle.contracts import (
    PlanEvidenceKind,
    PlanEvidenceReference,
    PlanRejection,
)
from fam_os.core.lifecycle.service import PlanLifecycleService


@dataclass(slots=True)
class AttemptTransitionService:
    lifecycle: PlanLifecycleService
    policies: AttemptPolicyRegistry
    replay: AttemptReplayRegistry

    def transition_after_failure(
        self, command: AttemptTransitionCommand
    ) -> AttemptTransitionResult:
        snapshot = self.lifecycle.repository.get(command.plan_instance_id)
        rejection = _snapshot_rejection(snapshot, command.expected_revision)
        if rejection is not None:
            return _rejected(command.plan_instance_id, rejection)
        if not _route_context_matches(snapshot, command.routed):
            return _rejected(command.plan_instance_id, AttemptRejection.INVALID_CONTEXT)
        target = _failure_target(snapshot)
        policy = self.policies.get(snapshot.plan.plan_id)
        classified = _classify(policy, target)
        if classified is None or not _valid_target(target, command.routed):
            return _rejected(command.plan_instance_id, AttemptRejection.INVALID_STEP)
        kind, limit = classified
        if _attempt_count(snapshot, kind) >= limit:
            return _rejected(command.plan_instance_id, AttemptRejection.BUDGET_EXHAUSTED)
        attempt_ids = (command.failed_attempt_id, command.next_attempt_id)
        if not self.replay.reserve(attempt_ids):
            return _rejected(command.plan_instance_id, AttemptRejection.REPLAYED)
        references = _references(command, kind, target.capability_ids[0])
        advanced = self.lifecycle.advance(
            command.plan_instance_id, command.expected_revision,
            StepOutcome.FAILED, references,
        )
        if advanced.rejection is not None:
            return _rejected(command.plan_instance_id, advanced.rejection)
        return AttemptTransitionResult(command.plan_instance_id, kind, advanced.snapshot)


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


def _failure_target(snapshot):
    matches = tuple(
        transition.target_step_id for transition in snapshot.plan.transitions
        if transition.source_step_id == snapshot.current_step_id
        and transition.outcome is StepOutcome.FAILED
    )
    if len(matches) != 1:
        return None
    return _step(snapshot.plan, matches[0])


def _classify(policy, target):
    if policy is None or target is None:
        return None
    if target.step_id in policy.repair_step_ids:
        return AttemptKind.REPAIR, policy.max_repairs
    if target.step_id in policy.escalation_step_ids:
        return AttemptKind.ESCALATION, policy.max_escalations
    return None


def _valid_target(target, routed) -> bool:
    return (
        target.kind is PlanStepKind.INFERENCE
        and len(target.capability_ids) == 1
        and set(target.capability_ids).issubset(
            routed.admitted.permission.authorized_capabilities
        )
    )


def _attempt_count(snapshot, kind) -> int:
    evidence_kind = (
        PlanEvidenceKind.REPAIR_ATTEMPT
        if kind is AttemptKind.REPAIR else PlanEvidenceKind.ESCALATION_ATTEMPT
    )
    return sum(
        reference.kind is evidence_kind
        for event in snapshot.events for reference in event.evidence_refs
    )


def _references(command, kind, capability_id):
    next_kind = (
        PlanEvidenceKind.REPAIR_ATTEMPT
        if kind is AttemptKind.REPAIR else PlanEvidenceKind.ESCALATION_ATTEMPT
    )
    return (
        PlanEvidenceReference(
            command.failed_attempt_id, PlanEvidenceKind.FAILED_ATTEMPT, capability_id
        ),
        PlanEvidenceReference(command.next_attempt_id, next_kind, capability_id),
    )


def _step(plan, step_id):
    return next(step for step in plan.steps if step.step_id == step_id)


def _rejected(instance_id, rejection):
    return AttemptTransitionResult(instance_id, rejection=rejection)
