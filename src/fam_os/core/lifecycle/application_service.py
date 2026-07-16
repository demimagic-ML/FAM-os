"""Authorized observation and action-proposal plan-step coordination."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fam_os.applications import (
    ActionPreparationRequest,
    ActionProposal,
    ApplicationAuthority,
    CapabilityKind,
    CapabilityDescriptor,
    ObservationRequest,
    ObservationResult,
    ObservationStatus,
    PermissionGrant,
)
from fam_os.core.contracts import PlanStepKind, StepOutcome
from fam_os.core.lifecycle.application_contracts import (
    ActionProposalAcquisition,
    ApplicationStepRejection,
    ApplicationStepResult,
    ObservationAcquisition,
)
from fam_os.core.lifecycle.application_authorization import (
    grant_allows as _shared_grant_allows,
    route_context_matches as _route_context_matches,
    snapshot_rejection as _snapshot_rejection,
    valid_capability as _valid_capability,
)
from fam_os.core.lifecycle.application_ports import (
    ApplicationEvidenceProvider,
    ApplicationPermissionRegistry,
)
from fam_os.core.lifecycle.contracts import (
    PlanEvidenceKind,
    PlanEvidenceReference,
    PlanInstanceSnapshot,
)
from fam_os.core.lifecycle.service import PlanLifecycleService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _identifier() -> str:
    return str(uuid4())


@dataclass(frozen=True, slots=True)
class _AuthorizedStep:
    snapshot: PlanInstanceSnapshot
    capability: CapabilityDescriptor
    grant: PermissionGrant


@dataclass(slots=True)
class ApplicationStepService:
    lifecycle: PlanLifecycleService
    provider: ApplicationEvidenceProvider
    permissions: ApplicationPermissionRegistry
    clock: Callable[[], datetime] = _utc_now
    evidence_id_factory: Callable[[], str] = _identifier

    def acquire_observation(self, command: ObservationAcquisition) -> ApplicationStepResult:
        authorized, rejection = self._authorize(
            command, PlanStepKind.OBSERVE, CapabilityKind.OBSERVATION,
            ApplicationAuthority.OBSERVE,
        )
        if rejection is not None:
            return _rejected(command.plan_instance_id, rejection)
        request = ObservationRequest(
            self.evidence_id_factory(), command.application_instance_id,
            authorized.capability.capability_id, command.permission_grant_id,
            command.parameters, command.resource_uri,
        )
        try:
            evidence = self.provider.observe(request)
        except Exception:
            return _rejected(
                command.plan_instance_id, ApplicationStepRejection.PROVIDER_UNAVAILABLE
            )
        if not _valid_observation(evidence, request):
            return _rejected(
                command.plan_instance_id, ApplicationStepRejection.INVALID_EVIDENCE
            )
        outcome = _observation_outcome(evidence.status)
        return self._advance(
            command, evidence, outcome, PlanEvidenceKind.OBSERVATION,
            authorized.capability.capability_id,
        )

    def acquire_action_proposal(
        self, command: ActionProposalAcquisition
    ) -> ApplicationStepResult:
        authorized, rejection = self._authorize(
            command, PlanStepKind.PREPARE_ACTION, CapabilityKind.ACTION,
            ApplicationAuthority.PROPOSE,
        )
        if rejection is not None:
            return _rejected(command.plan_instance_id, rejection)
        request = ActionPreparationRequest(
            self.evidence_id_factory(), command.application_instance_id,
            authorized.capability.capability_id, command.permission_grant_id,
            command.summary, command.parameters, command.resource_uri,
            command.expected_resource_revision,
        )
        try:
            evidence = self.provider.prepare_action(request)
        except Exception:
            return _rejected(
                command.plan_instance_id, ApplicationStepRejection.PROVIDER_UNAVAILABLE
            )
        if not _valid_proposal(evidence, request, authorized.capability):
            return _rejected(
                command.plan_instance_id, ApplicationStepRejection.INVALID_EVIDENCE
            )
        return self._advance(
            command, evidence, StepOutcome.SUCCEEDED,
            PlanEvidenceKind.ACTION_PROPOSAL, authorized.capability.capability_id,
        )

    def _authorize(self, command, step_kind, capability_kind, authority):
        snapshot = self.lifecycle.repository.get(command.plan_instance_id)
        plan_rejection = _snapshot_rejection(snapshot, command.expected_revision)
        if plan_rejection is not None:
            return None, plan_rejection
        now = self.clock()
        if now >= snapshot.authority_binding.valid_until:
            return None, ApplicationStepRejection.PERMISSION_DENIED
        if not _route_context_matches(snapshot, command.routed):
            return None, ApplicationStepRejection.INVALID_CONTEXT
        step = _step(snapshot.plan, snapshot.current_step_id)
        if step.kind is not step_kind or len(step.capability_ids) != 1:
            return None, ApplicationStepRejection.INVALID_STEP
        try:
            capability = self.provider.capability(
                command.application_instance_id, step.capability_ids[0]
            )
        except Exception:
            return None, ApplicationStepRejection.CAPABILITY_UNAVAILABLE
        if not _valid_capability(
            capability, capability_kind, command.application_instance_id,
            step.capability_ids[0],
        ):
            return None, ApplicationStepRejection.CAPABILITY_UNAVAILABLE
        try:
            grant = self.permissions.get(command.permission_grant_id)
        except Exception:
            return None, ApplicationStepRejection.PERMISSION_DENIED
        if not _shared_grant_allows(
            grant, command.routed, capability, authority, command.resource_uri, now
        ):
            return None, ApplicationStepRejection.PERMISSION_DENIED
        return _AuthorizedStep(snapshot, capability.capability, grant), None

    def _advance(self, command, evidence, outcome, evidence_kind, capability_id):
        reference_id = (
            evidence.request_id if isinstance(evidence, ObservationResult)
            else evidence.proposal_id
        )
        reference = PlanEvidenceReference(
            reference_id, evidence_kind, capability_id, command.permission_grant_id
        )
        advanced = self.lifecycle.advance(
            command.plan_instance_id, command.expected_revision, outcome, (reference,)
        )
        if advanced.rejection is not None:
            return _rejected(command.plan_instance_id, advanced.rejection)
        return ApplicationStepResult(
            command.plan_instance_id, advanced.snapshot, evidence
        )


def _valid_proposal(evidence, request, capability) -> bool:
    if not isinstance(evidence, ActionProposal) or evidence.request != request:
        return False
    postconditions = tuple(item.condition_id for item in evidence.postconditions)
    return (
        evidence.reversibility is capability.reversibility
        and evidence.confirmation is capability.confirmation
        and postconditions == capability.postcondition_ids
    )


def _valid_observation(evidence, request) -> bool:
    return (
        isinstance(evidence, ObservationResult)
        and isinstance(evidence.status, ObservationStatus)
        and evidence.request_id == request.request_id
        and (
            evidence.status is not ObservationStatus.OBSERVED
            or request.resource_uri is None
            or evidence.resource_uri == request.resource_uri
        )
    )


def _observation_outcome(status):
    return {
        ObservationStatus.OBSERVED: StepOutcome.SUCCEEDED,
        ObservationStatus.DENIED: StepOutcome.DENIED,
        ObservationStatus.UNAVAILABLE: StepOutcome.UNAVAILABLE,
        ObservationStatus.FAILED: StepOutcome.FAILED,
    }[status]


def _step(plan, step_id):
    return next(step for step in plan.steps if step.step_id == step_id)


def _rejected(instance_id, rejection):
    return ApplicationStepResult(instance_id, rejection=rejection)
