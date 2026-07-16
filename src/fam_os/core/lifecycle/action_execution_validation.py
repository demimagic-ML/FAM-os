"""Exact authority and evidence validation before application mutation."""

from dataclasses import dataclass

from fam_os.applications import (
    ActionConfirmation, ActionProposal, CapabilityKind, CapabilityRegistryEntry,
    ConfirmationDecision, PermissionGrant,
)
from fam_os.core.contracts import PlanStepKind
from fam_os.core.lifecycle.action_execution_contracts import (
    ActionExecutionCommand, ActionExecutionRejection,
)
from fam_os.core.lifecycle.application_authorization import (
    grant_allows, route_context_matches, snapshot_rejection, valid_capability,
)
from fam_os.core.lifecycle.contracts import PlanEvidenceKind


@dataclass(frozen=True, slots=True)
class AuthorizedActionExecution:
    snapshot: object
    entry: CapabilityRegistryEntry
    grant: PermissionGrant


def authorize_action_execution(lifecycle, provider, permissions, command, now):
    snapshot = lifecycle.repository.get(command.plan_instance_id)
    rejection = snapshot_rejection(snapshot, command.expected_revision)
    if rejection is not None:
        return None, rejection
    if now >= snapshot.authority_binding.valid_until:
        return None, ActionExecutionRejection.PERMISSION_DENIED
    if not route_context_matches(snapshot, command.routed):
        return None, ActionExecutionRejection.INVALID_CONTEXT
    step = next(item for item in snapshot.plan.steps if item.step_id == snapshot.current_step_id)
    if step.kind is not PlanStepKind.EXECUTE_ACTION or len(step.capability_ids) != 1:
        return None, ActionExecutionRejection.INVALID_STEP
    entry = _capability(provider, command.proposal, step.capability_ids[0])
    if entry is None:
        return None, ActionExecutionRejection.CAPABILITY_UNAVAILABLE
    grant = _grant(permissions, command.proposal)
    if not grant_allows(
        grant, command.routed, entry, entry.capability.required_authority,
        command.proposal.request.resource_uri, now,
    ):
        return None, ActionExecutionRejection.PERMISSION_DENIED
    if not _proposal_matches(command.proposal, entry):
        return None, ActionExecutionRejection.INVALID_EVIDENCE
    if step.acceptance_ids != tuple(
        item.condition_id for item in command.proposal.postconditions
    ):
        return None, ActionExecutionRejection.INVALID_EVIDENCE
    if not _confirmation_matches(snapshot, command, now):
        return None, ActionExecutionRejection.INVALID_EVIDENCE
    return AuthorizedActionExecution(snapshot, entry, grant), None


def _capability(provider, proposal, capability_id):
    try:
        entry = provider.capability(proposal.request.instance_id, capability_id)
    except Exception:
        return None
    if not valid_capability(
        entry, CapabilityKind.ACTION, proposal.request.instance_id, capability_id,
    ):
        return None
    return entry


def _grant(permissions, proposal):
    try:
        return permissions.get(proposal.request.permission_grant_id)
    except Exception:
        return None


def _proposal_matches(proposal: ActionProposal, entry) -> bool:
    request = proposal.request
    conditions = tuple(item.condition_id for item in proposal.postconditions)
    return (
        request.instance_id == entry.instance_id
        and request.capability_id == entry.capability_id
        and proposal.reversibility is entry.capability.reversibility
        and proposal.confirmation is entry.capability.confirmation
        and conditions == entry.capability.postcondition_ids
    )


def _confirmation_matches(snapshot, command: ActionExecutionCommand, now) -> bool:
    proposal = command.proposal
    confirmation = command.confirmation
    if not isinstance(confirmation, ActionConfirmation):
        return False
    if (
        confirmation.decision is not ConfirmationDecision.APPROVED
        or confirmation.proposal_id != proposal.proposal_id
        or confirmation.permission_grant_id != proposal.request.permission_grant_id
        or confirmation.decided_by != command.routed.admitted.permission.principal_id
        or confirmation.decided_at > now
    ):
        return False
    proposal_event = _evidence_event(
        snapshot, PlanEvidenceKind.ACTION_PROPOSAL, proposal.proposal_id,
        proposal.request.capability_id, proposal.request.permission_grant_id,
    )
    confirmation_event = _evidence_event(
        snapshot, PlanEvidenceKind.ACTION_CONFIRMATION, confirmation.confirmation_id,
        proposal.request.capability_id, proposal.request.permission_grant_id,
    )
    if proposal_event is None or confirmation_event is None:
        return False
    return (
        proposal_event.occurred_at <= confirmation.decided_at
        <= confirmation_event.occurred_at <= now
    )


def _evidence_event(snapshot, kind, reference_id, capability_id, grant_id):
    matches = tuple(
        event for event in snapshot.events
        if any(
            ref.kind is kind and ref.reference_id == reference_id
            and ref.capability_id == capability_id
            and ref.permission_grant_id == grant_id
            for ref in event.evidence_refs
        )
    )
    return matches[0] if len(matches) == 1 else None
