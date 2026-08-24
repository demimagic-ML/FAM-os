"""Production restart reconciliation for durable application mutations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from fam_os.applications import (
    ActionAuditStage,
    ActionResult,
    ActionStatus,
    ApplicationActionAuditIntent,
    ApplicationFailure,
    ApplicationFailureCategory,
    ApplicationRetryDisposition,
    ObservationRequest,
    ObservationStatus,
)
from fam_os.core.contracts import PlanStepKind, StepOutcome
from fam_os.core.lifecycle import (
    PlanEvidenceKind,
    PlanEvidenceReference,
    PlanLifecycleService,
)
from fam_os.core.production.application_contracts import ApplicationExecutionState
from fam_os.product.composition.owner_filesystem import (
    CREATE_CAPABILITY,
    INSPECT_CAPABILITY,
    REMOVE_CAPABILITY,
)
from fam_os.product.restart_recovery import (
    PersistedActionRecord,
    PersistedActionState,
    RestartDisposition,
    RestartRecoveryDecision,
    restart_decision,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProductionActionPostconditionReconciler:
    """Reconstruct only outcomes that can be proven without provider execution."""

    def __init__(self, provider, verifier, clock: Callable[[], datetime] = _utc_now):
        self._provider = provider
        self._verifier = verifier
        self._clock = clock

    def reconcile(self, proposal) -> ActionResult | None:
        capability_id = proposal.request.capability_id
        if capability_id not in {CREATE_CAPABILITY, REMOVE_CAPABILITY}:
            return None
        try:
            observed = self._provider.observe(ObservationRequest(
                f"restart-observation-{uuid4()}", proposal.request.instance_id,
                INSPECT_CAPABILITY, proposal.request.permission_grant_id, {},
                proposal.request.resource_uri,
            ))
            if observed.status is not ObservationStatus.OBSERVED:
                return None
            evidence = tuple(
                self._verifier.verify(requirement, proposal)
                for requirement in proposal.postconditions
            )
        except Exception:
            return None
        completed_at = self._clock()
        if all(item.passed for item in evidence):
            reversal_token = None
            if capability_id == CREATE_CAPABILITY:
                device = observed.payload.get("device")
                inode = observed.payload.get("inode")
                if (
                    not isinstance(device, int) or isinstance(device, bool)
                    or not isinstance(inode, int) or isinstance(inode, bool)
                    or device < 0 or inode < 1
                ):
                    return None
                reversal_token = json.dumps(
                    {"device": device, "inode": inode},
                    sort_keys=True, separators=(",", ":"),
                )
            return ActionResult(
                proposal.proposal_id, ActionStatus.VERIFIED, completed_at,
                evidence,
                {
                    "exists": observed.payload.get("exists"),
                    "empty": observed.payload.get("empty"),
                },
                after_revision=observed.revision,
                reversal_token=reversal_token,
            )
        failed_ids = tuple(item.condition_id for item in evidence if not item.passed)
        return ActionResult(
            proposal.proposal_id, ActionStatus.POSTCONDITION_FAILED, completed_at,
            evidence,
            after_revision=observed.revision,
            error=ApplicationFailure(
                ApplicationFailureCategory.POSTCONDITION_FAILED,
                "application.restart_postcondition_failed",
                "Restart reconciliation proved that action postconditions did not pass.",
                ApplicationRetryDisposition.AFTER_STATE_CHANGE,
                failed_ids,
            ),
        )


class ApplicationRestartCoordinator:
    """Synchronize action, application, plan, and audit state before serving clients."""

    def __init__(self, repositories, applications) -> None:
        self._repositories = repositories
        self._applications = applications
        self._postconditions = ProductionActionPostconditionReconciler(
            applications.provider, applications.verifier,
        )

    def reconcile(self) -> tuple[RestartRecoveryDecision, ...]:
        decisions = []
        for record in self._repositories.actions.recoverable():
            decision = restart_decision(record)
            if decision.disposition is RestartDisposition.REQUIRE_FRESH_APPROVAL:
                self._require_fresh_approval(record)
            elif decision.disposition is RestartDisposition.RECONCILE_POSTCONDITIONS:
                decision = self._reconcile_postconditions(record, decision)
            decisions.append(decision)
        return tuple(decisions)

    def _require_fresh_approval(self, record: PersistedActionRecord) -> None:
        application, snapshot = self._state(record)
        step = _current_step(snapshot)
        if step.kind not in {PlanStepKind.CONFIRM_ACTION, PlanStepKind.EXECUTE_ACTION}:
            raise RuntimeError("recoverable approval is not at a confirmation boundary")
        replacement = replace(
            record, state=PersistedActionState.AWAITING_APPROVAL,
            confirmation_id=None,
        )
        if replacement != record and not self._repositories.actions.replace(
            record.state, replacement,
        ):
            raise RuntimeError("action changed during production restart reconciliation")
        application_replacement = replace(
            application, revision=application.revision + 1,
            state=ApplicationExecutionState.WAITING_APPROVAL,
            confirmation=None,
        )
        if (
            application.state is not ApplicationExecutionState.WAITING_APPROVAL
            or application.confirmation is not None
        ):
            self._replace_application(application, application_replacement)

    def _reconcile_postconditions(
        self, record: PersistedActionRecord, decision: RestartRecoveryDecision,
    ) -> RestartRecoveryDecision:
        application, snapshot = self._state(record)
        application = self._mark_recovery_required(application)
        reconciling = replace(
            record, state=PersistedActionState.RECONCILIATION_REQUIRED,
            confirmation_id=None,
        )
        if not self._repositories.actions.replace(record.state, reconciling):
            raise RuntimeError("action changed while entering restart reconciliation")
        result = self._postconditions.reconcile(record.proposal)
        if result is None:
            return decision
        snapshot = self._commit_execution_evidence(application, reconciling, result, snapshot)
        if snapshot is None:
            return decision
        self._replace_application(application, replace(
            application, revision=application.revision + 1,
            state=ApplicationExecutionState.ACTIVE,
            confirmation=None, action_result=result,
        ))
        final_state = (
            PersistedActionState.VERIFIED
            if result.verified else PersistedActionState.FAILED
        )
        if not self._repositories.actions.replace(
            reconciling.state, replace(reconciling, state=final_state, result=result),
        ):
            raise RuntimeError("action changed while committing restart reconciliation")
        return replace(decision, resulting_state=final_state)

    def _mark_recovery_required(self, application):
        if (
            application.state is ApplicationExecutionState.RECOVERY_REQUIRED
            and application.confirmation is None
        ):
            return application
        replacement = replace(
            application, revision=application.revision + 1,
            state=ApplicationExecutionState.RECOVERY_REQUIRED,
            confirmation=None,
        )
        self._replace_application(application, replacement)
        return replacement

    def _commit_execution_evidence(self, application, action, result, snapshot):
        existing = _execution_event(snapshot, action)
        if existing is not None:
            audit_ids = tuple(
                reference.reference_id for reference in existing.evidence_refs
                if reference.kind is PlanEvidenceKind.ACTION_AUDIT
            )
            if audit_ids and all(
                self._applications.audit.contains_event(event_id)
                for event_id in audit_ids
            ):
                return snapshot
            return None
        step = _current_step(snapshot)
        if step.kind is not PlanStepKind.EXECUTE_ACTION:
            return None
        operation_id, event_id = _recovery_ids(action.action_id)
        intent = self._audit_intent(
            application, action, result, operation_id, event_id,
        )
        if not self._applications.audit.contains_event(event_id):
            self._applications.audit.append(intent)
        references = (
            PlanEvidenceReference(
                operation_id, PlanEvidenceKind.ACTION_RESULT,
                action.proposal.request.capability_id,
                action.proposal.request.permission_grant_id,
            ),
            PlanEvidenceReference(
                event_id, PlanEvidenceKind.ACTION_AUDIT,
                action.proposal.request.capability_id,
                action.proposal.request.permission_grant_id,
            ),
        )
        advanced = PlanLifecycleService(self._repositories.plans).advance(
            snapshot.instance_id, snapshot.revision,
            StepOutcome.SUCCEEDED if result.verified else StepOutcome.FAILED,
            references,
        )
        return advanced.snapshot if advanced.rejection is None else None

    def _audit_intent(self, application, action, result, operation_id, event_id):
        proposal = action.proposal
        entry = self._applications.provider.capability(
            proposal.request.instance_id, proposal.request.capability_id,
        )
        if entry is None:
            raise RuntimeError("reconciled action capability is unavailable")
        permission = application.routed.admitted.permission
        resource = proposal.request.resource_uri
        stage = (
            ActionAuditStage.VERIFIED
            if result.verified else ActionAuditStage.POSTCONDITION_FAILED
        )
        return ApplicationActionAuditIntent(
            event_id, operation_id, result.completed_at,
            application.routed.request_id, application.instance_id,
            permission.principal_id, permission.session_id,
            entry.application_id, entry.instance_id, entry.capability_id,
            proposal.request.permission_grant_id, proposal.proposal_id,
            f"confirmation-recovery-observed-{_digest(action.action_id)}",
            stage,
            hashlib.sha256(resource.encode()).hexdigest() if resource else None,
            tuple(item.condition_id for item in result.postcondition_evidence),
            result.status, proposal.reversal_capability_id,
            result.reversal_token is not None,
            None if result.error is None else result.error.code,
        )

    def _state(self, record):
        application = self._repositories.application_executions.get(record.plan_id)
        snapshot = self._repositories.plans.get(record.plan_id)
        if application is None or snapshot is None:
            raise RuntimeError("persisted action has no durable application plan")
        if application.proposal != record.proposal:
            raise RuntimeError("persisted action and application proposal disagree")
        return application, snapshot

    def _replace_application(self, current, replacement) -> None:
        if not self._repositories.application_executions.replace(
            current.revision, replacement,
        ):
            raise RuntimeError("application changed during restart reconciliation")


def _current_step(snapshot):
    return next(
        step for step in snapshot.plan.steps
        if step.step_id == snapshot.current_step_id
    )


def _execution_event(snapshot, action):
    execute_ids = {
        step.step_id for step in snapshot.plan.steps
        if step.kind is PlanStepKind.EXECUTE_ACTION
        and action.proposal.request.capability_id in step.capability_ids
    }
    matches = tuple(
        event for event in snapshot.events
        if event.source_step_id in execute_ids
        and event.outcome in {StepOutcome.SUCCEEDED, StepOutcome.FAILED}
        and any(
            reference.kind is PlanEvidenceKind.ACTION_RESULT
            and reference.capability_id == action.proposal.request.capability_id
            and reference.permission_grant_id
            == action.proposal.request.permission_grant_id
            for reference in event.evidence_refs
        )
    )
    return matches[0] if len(matches) == 1 else None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def _recovery_ids(action_id: str) -> tuple[str, str]:
    digest = _digest(action_id)
    return f"action-recovery-{digest}", f"action-recovery-audit-{digest}"
