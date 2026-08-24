"""Shell-facing approval and admission facade for application tasks."""

from dataclasses import replace
from datetime import datetime, timezone
import json
from uuid import uuid4

from fam_os.applications import (
    ActionConfirmation,
    ActionResult,
    ActionStatus,
    ApplicationFailure,
    ApplicationFailureCategory,
    ApplicationRetryDisposition,
    ConfirmationDecision,
    Reversibility,
)
from fam_os.applications.payloads import thaw_payload
from fam_os.core.ingress.shell_views import accepted_shell_snapshot, project_shell_snapshot
from fam_os.core.contracts import StepOutcome
from fam_os.core.lifecycle import (
    ConfirmationCommand, PlanEvidenceKind, PlanEvidenceReference,
    PlanLifecycleService,
)
from fam_os.core.production.application_admission import ApplicationRequestStarter
from fam_os.core.production.application_contracts import ApplicationExecutionState
from fam_os.core.production.contracts import RuntimeModelSelection
from fam_os.core.production.application_reversal import ApplicationReversalService
from fam_os.core.production.execution_state import terminal_execution
from fam_os.product.restart_recovery import PersistedActionState
from fam_os.shell import ShellApprovalRequest, ShellDecision


class ApplicationShellGateway:
    def __init__(
        self, repositories, applications, classifier, selector, capacity,
        inference, budget,
    ) -> None:
        self._repositories = repositories
        self._applications = applications
        self._classifier = classifier
        self._selector = selector
        self._capacity = capacity
        self._inference = inference
        self._budget = budget
        self.reversals = ApplicationReversalService(
            repositories, applications, classifier, budget,
        )

    def ask(self, command, intent, deterministic_parameters=None):
        capacity = self._capacity()
        selection = (
            self._selector.select(
                command.request_id, intent, capacity,
                resident_model_refs=self._inference.resident_models(),
            )
            if deterministic_parameters is None else
            RuntimeModelSelection(
                f"selection-{command.request_id}-deterministic", command.request_id,
                intent, "internal:application-action", "deterministic", 0,
                capacity.available_host_bytes, capacity.available_vram_bytes,
                ("model_not_invoked",),
            )
        )
        instance_id = f"task-{command.request_id}"
        ApplicationRequestStarter(
            self._repositories, self._applications, self._classifier,
        ).start(
            command, intent, selection, instance_id,
            seeded_candidate_content=deterministic_parameters,
        )
        self._budget(instance_id)
        return accepted_shell_snapshot(
            instance_id, command.request_id,
            (
                "Accepted deterministic application action; no model was invoked."
                if deterministic_parameters is not None else
                f"Accepted application task; selected {selection.model_ref}"
            ),
        )

    def approval_view(self, session_id, snapshot):
        application = self._repositories.application_executions.get(session_id)
        if application is None:
            return None
        if (
            application.state is not ApplicationExecutionState.WAITING_APPROVAL
            or application.proposal is None
        ):
            return None
        proposal = application.proposal
        grant = self._repositories.application_permissions.get(
            application.permission_grant_id,
        )
        if grant is None or grant.expires_at is None:
            raise RuntimeError("application approval grant is unavailable")
        approval = ShellApprovalRequest(
            f"approval-{proposal.proposal_id}", proposal.proposal_id,
            proposal.request.capability_id,
            json.dumps(thaw_payload(proposal.preview), sort_keys=True),
            grant.expires_at,
            proposal.reversibility is not Reversibility.IRREVERSIBLE,
        )
        recovering = snapshot.current_step_id.startswith("execute-action-")
        return project_shell_snapshot(
            session_id, snapshot, snapshot.revision + 1, approval=approval,
            message=(
                "The service restarted before execution. Prior approval was discarded; "
                "review the deterministic preview and approve again."
                if recovering else
                "Review the deterministic action preview before approval."
            ),
        )

    def blocking_view(self, session_id, snapshot):
        application = self._repositories.application_executions.get(session_id)
        if application is None:
            return None
        if application.state is ApplicationExecutionState.WAITING_APPROVAL:
            return self.approval_view(session_id, snapshot)
        if application.state is ApplicationExecutionState.RECOVERY_REQUIRED:
            return project_shell_snapshot(
                session_id, snapshot, snapshot.revision + 1,
                message=(
                    "Action outcome is uncertain after restart. FAM_OS did not retry the "
                    "provider and requires deterministic postcondition reconciliation."
                ),
            )
        return None

    def decide(self, command):
        application = self._repositories.application_executions.get(command.session_id)
        snapshot = self._repositories.plans.get(command.session_id)
        if application is None or snapshot is None or application.proposal is None:
            raise ValueError("application approval does not exist")
        if application.state is not ApplicationExecutionState.WAITING_APPROVAL:
            raise ValueError("application is not awaiting approval")
        if command.expected_revision != snapshot.revision + 1:
            raise ValueError("application approval revision is stale")
        approval_id = f"approval-{application.proposal.proposal_id}"
        if command.approval_id != approval_id:
            raise ValueError("application approval identity does not match")
        recovering = snapshot.current_step_id.startswith("execute-action-")
        confirmation = _confirmation(application, command, recovering)
        transition = (
            self._applications.confirmations.record_reapproval
            if recovering else self._applications.confirmations.record_confirmation
        )
        outcome = transition(
            ConfirmationCommand(
                application.instance_id, snapshot.revision,
                application.routed, confirmation,
            )
        )
        if outcome.rejection is not None:
            raise ValueError(f"application confirmation rejected: {outcome.rejection}")
        self._record(application, confirmation)
        if outcome.snapshot.terminal:
            inference = self._repositories.inference_executions.get(command.session_id)
            if inference is None:
                raise RuntimeError("application inference state is missing")
            inference = terminal_execution(
                self._repositories, inference, "application.action.denied",
            )
        else:
            inference = None
        return outcome.snapshot, inference

    def cancel(self, command, snapshot):
        application = self._repositories.application_executions.get(command.session_id)
        inference = self._repositories.inference_executions.get(command.session_id)
        if application is None or inference is None:
            raise ValueError("application task does not exist")
        if command.expected_revision not in {0, snapshot.revision + 1}:
            raise ValueError("task cancellation revision is stale")
        action = self._action(application)
        if action is not None and action.state in {
            PersistedActionState.INVOKING, PersistedActionState.UNCERTAIN,
        }:
            raise ValueError("an invoked action must be reconciled before cancellation")
        reference = PlanEvidenceReference(
            f"cancel-{application.request_id}-{snapshot.revision}",
            PlanEvidenceKind.CANCELLATION, None,
        )
        advanced = PlanLifecycleService(self._repositories.plans).advance(
            snapshot.instance_id, snapshot.revision, StepOutcome.CANCELLED, (reference,),
        )
        if advanced.rejection is not None:
            raise ValueError("task cannot be cancelled in its current state")
        if action is not None and action.state not in {
            PersistedActionState.VERIFIED, PersistedActionState.FAILED,
            PersistedActionState.CANCELLED,
        }:
            replacement = replace(
                action, state=PersistedActionState.CANCELLED,
                result=_cancelled_result(application),
            )
            if not self._repositories.actions.replace(action.state, replacement):
                raise RuntimeError("application action changed during cancellation")
        self._repositories.application_permissions.revoke(
            application.permission_grant_id, datetime.now(timezone.utc),
        )
        self._replace_application(application, replace(
            application, revision=application.revision + 1,
            state=ApplicationExecutionState.TERMINAL,
        ))
        terminal = terminal_execution(
            self._repositories, inference, "core.request.cancelled",
        )
        return advanced.snapshot, terminal

    def _record(self, application, confirmation):
        approved = confirmation.decision is ConfirmationDecision.APPROVED
        updated = replace(
            application, revision=application.revision + 1,
            state=(
                ApplicationExecutionState.ACTIVE if approved
                else ApplicationExecutionState.TERMINAL
            ),
            confirmation=confirmation,
        )
        if not self._repositories.application_executions.replace(
            application.revision, updated,
        ):
            raise RuntimeError("application approval state changed")
        action_id = f"action-{application.proposal.proposal_id}"
        action = self._repositories.actions.get(action_id)
        if action is None:
            raise RuntimeError("persisted action proposal is missing")
        replacement = (
            replace(
                action, state=PersistedActionState.APPROVED,
                confirmation_id=confirmation.confirmation_id,
            )
            if approved else replace(
                action, state=PersistedActionState.CANCELLED,
                result=_denied_result(application, confirmation),
            )
        )
        if not self._repositories.actions.replace(action.state, replacement):
            raise RuntimeError("persisted action approval state changed")

    def _action(self, application):
        if application.proposal is None:
            return None
        return self._repositories.actions.get(f"action-{application.proposal.proposal_id}")

    def _replace_application(self, current, updated):
        if not self._repositories.application_executions.replace(
            current.revision, updated,
        ):
            raise RuntimeError("application execution state changed")


def _confirmation(application, command, recovering=False):
    approved = command.decision is ShellDecision.APPROVE
    return ActionConfirmation(
        (
            f"confirmation-recovery-{uuid4()}"
            if recovering else f"confirmation-{application.proposal.proposal_id}"
        ),
        application.proposal.proposal_id, application.permission_grant_id,
        ConfirmationDecision.APPROVED if approved else ConfirmationDecision.DENIED,
        "local-owner", datetime.now(timezone.utc),
        None if approved else "Denied by local owner.",
    )


def _denied_result(application, confirmation):
    return ActionResult(
        application.proposal.proposal_id, ActionStatus.DENIED,
        confirmation.decided_at,
        error=ApplicationFailure(
            ApplicationFailureCategory.PERMISSION_DENIED,
            "application.confirmation.denied", "Denied by local owner.",
            ApplicationRetryDisposition.AFTER_USER_ACTION,
        ),
    )


def _cancelled_result(application):
    return ActionResult(
        application.proposal.proposal_id, ActionStatus.CANCELLED,
        datetime.now(timezone.utc),
        error=ApplicationFailure(
            ApplicationFailureCategory.CANCELLED,
            "application.request.cancelled", "Cancelled by local owner.",
            ApplicationRetryDisposition.NEVER,
        ),
    )
