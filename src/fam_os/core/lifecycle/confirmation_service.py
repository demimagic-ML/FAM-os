"""Replay-safe approval, denial, and permission-expiry transitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fam_os.applications import (
    ApplicationAuthority,
    ConfirmationDecision,
    PermissionGrant,
)
from fam_os.core.contracts import PlanStepKind, StepOutcome
from fam_os.core.lifecycle.application_ports import ApplicationPermissionRegistry
from fam_os.core.lifecycle.confirmation_contracts import (
    ConfirmationCommand,
    ConfirmationDisposition,
    ConfirmationRejection,
    ConfirmationTransitionResult,
    PermissionExpiryCommand,
)
from fam_os.core.lifecycle.confirmation_ports import ConfirmationReplayRegistry
from fam_os.core.lifecycle.contracts import (
    PlanEvidenceKind,
    PlanEvidenceReference,
    PlanRejection,
)
from fam_os.core.lifecycle.service import PlanLifecycleService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier() -> str:
    return str(uuid4())


@dataclass(slots=True)
class ConfirmationTransitionService:
    lifecycle: PlanLifecycleService
    permissions: ApplicationPermissionRegistry
    replay: ConfirmationReplayRegistry
    clock: Callable[[], datetime] = _utc_now
    evidence_id_factory: Callable[[], str] = _identifier

    def record_confirmation(
        self, command: ConfirmationCommand
    ) -> ConfirmationTransitionResult:
        context, rejection = self._context(command)
        if rejection is not None:
            return _rejected(command.plan_instance_id, rejection)
        snapshot, step, proposal, proposal_time, grant = context
        now = self.clock()
        if _permission_inactive(snapshot, grant, now):
            return self._expire(command, step, proposal)
        confirmation = command.confirmation
        if not _valid_confirmation(
            confirmation, command, proposal, proposal_time, grant, now
        ):
            return _rejected(
                command.plan_instance_id, ConfirmationRejection.INVALID_CONFIRMATION
            )
        outcome, disposition = _confirmation_outcome(confirmation.decision)
        if not _has_transition(snapshot.plan, step.step_id, outcome):
            return _rejected(command.plan_instance_id, PlanRejection.ILLEGAL_OUTCOME)
        if not self.replay.reserve(confirmation.confirmation_id):
            return _rejected(command.plan_instance_id, ConfirmationRejection.REPLAYED)
        reference = PlanEvidenceReference(
            confirmation.confirmation_id, PlanEvidenceKind.ACTION_CONFIRMATION,
            step.capability_ids[0], proposal.permission_grant_id,
        )
        return self._advance(command, outcome, disposition, reference, confirmation)

    def record_permission_expiry(
        self, command: PermissionExpiryCommand
    ) -> ConfirmationTransitionResult:
        context, rejection = self._context(command)
        if rejection is not None:
            return _rejected(command.plan_instance_id, rejection)
        snapshot, step, proposal, _proposal_time, grant = context
        if not _permission_inactive(snapshot, grant, self.clock()):
            return _rejected(command.plan_instance_id, ConfirmationRejection.NOT_EXPIRED)
        return self._expire(command, step, proposal)

    def _context(self, command):
        snapshot = self.lifecycle.repository.get(command.plan_instance_id)
        rejection = _snapshot_rejection(snapshot, command.expected_revision)
        if rejection is not None:
            return None, rejection
        if not _route_context_matches(snapshot, command.routed):
            return None, ConfirmationRejection.INVALID_CONTEXT
        step = _step(snapshot.plan, snapshot.current_step_id)
        if step.kind is not PlanStepKind.CONFIRM_ACTION or len(step.capability_ids) != 1:
            return None, ConfirmationRejection.INVALID_STEP
        proposal = _proposal_reference(snapshot, step.capability_ids[0])
        if proposal is None:
            return None, ConfirmationRejection.INVALID_STEP
        try:
            grant = self.permissions.get(proposal.permission_grant_id)
        except Exception:
            grant = None
        if grant is not None and not _grant_identity_matches(grant, command.routed):
            return None, ConfirmationRejection.PERMISSION_DENIED
        return (
            snapshot, step, proposal, snapshot.events[-1].occurred_at, grant
        ), None

    def _expire(self, command, step, proposal):
        if not _has_transition(
            self.lifecycle.repository.get(command.plan_instance_id).plan,
            step.step_id, StepOutcome.EXPIRED,
        ):
            return _rejected(command.plan_instance_id, PlanRejection.ILLEGAL_OUTCOME)
        reference = PlanEvidenceReference(
            self.evidence_id_factory(), PlanEvidenceKind.PERMISSION_EXPIRY,
            step.capability_ids[0], proposal.permission_grant_id,
        )
        return self._advance(
            command, StepOutcome.EXPIRED, ConfirmationDisposition.EXPIRED, reference
        )

    def _advance(self, command, outcome, disposition, reference, confirmation=None):
        advanced = self.lifecycle.advance(
            command.plan_instance_id, command.expected_revision, outcome, (reference,)
        )
        if advanced.rejection is not None:
            return _rejected(command.plan_instance_id, advanced.rejection)
        return ConfirmationTransitionResult(
            command.plan_instance_id, disposition, advanced.snapshot, confirmation
        )


def _snapshot_rejection(snapshot, expected_revision):
    if snapshot is None:
        return PlanRejection.NOT_FOUND
    if snapshot.revision != expected_revision:
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
        and snapshot.plan.route.required_capabilities
        == routed.admitted.permission.authorized_capabilities
    )


def _proposal_reference(snapshot, capability_id):
    matches = tuple(
        reference for reference in snapshot.events[-1].evidence_refs
        if reference.kind is PlanEvidenceKind.ACTION_PROPOSAL
        and reference.capability_id == capability_id
    )
    return matches[0] if len(matches) == 1 else None


def _grant_identity_matches(grant, routed) -> bool:
    return (
        isinstance(grant, PermissionGrant)
        and grant.subject_id == routed.admitted.permission.principal_id
        and ApplicationAuthority.PROPOSE in grant.authorities
    )


def _permission_inactive(snapshot, grant, now) -> bool:
    return (
        now >= snapshot.authority_binding.valid_until
        or not isinstance(grant, PermissionGrant)
        or not grant.active_at(now)
    )


def _valid_confirmation(confirmation, command, proposal, proposal_time, grant, now) -> bool:
    return (
        isinstance(confirmation.decision, ConfirmationDecision)
        and confirmation.proposal_id == proposal.reference_id
        and confirmation.permission_grant_id == proposal.permission_grant_id
        and confirmation.decided_by == command.routed.admitted.permission.principal_id
        and confirmation.decided_at >= proposal_time
        and confirmation.decided_at <= now
        and grant.active_at(confirmation.decided_at)
    )


def _confirmation_outcome(decision):
    if decision is ConfirmationDecision.APPROVED:
        return StepOutcome.SUCCEEDED, ConfirmationDisposition.APPROVED
    return StepOutcome.DENIED, ConfirmationDisposition.DENIED


def _has_transition(plan, source_step_id, outcome) -> bool:
    return any(
        transition.source_step_id == source_step_id and transition.outcome is outcome
        for transition in plan.transitions
    )


def _step(plan, step_id):
    return next(step for step in plan.steps if step.step_id == step_id)


def _rejected(instance_id, rejection):
    return ConfirmationTransitionResult(instance_id, rejection=rejection)
