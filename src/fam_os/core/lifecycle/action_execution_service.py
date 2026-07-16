"""Required safety, verification, recovery, and audit envelope for app actions."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4

from fam_os.applications import ActionStatus
from fam_os.core.contracts import StepOutcome
from fam_os.core.lifecycle.action_audit_policy import requested_audit, terminal_audit
from fam_os.core.lifecycle.action_execution_contracts import (
    ActionExecutionRejection, ActionExecutionResult,
)
from fam_os.core.lifecycle.action_execution_validation import authorize_action_execution
from fam_os.core.lifecycle.action_result_policy import (
    audit_failure_result, evaluate_conditions, finalize_provider_result,
    precondition_result, provider_failure_result, recovery_metadata,
)
from fam_os.core.lifecycle.contracts import PlanEvidenceKind, PlanEvidenceReference


def _utc_now():
    return datetime.now(timezone.utc)


def _identifier():
    return str(uuid4())


@dataclass(slots=True)
class ApplicationActionExecutionService:
    lifecycle: object
    provider: object
    permissions: object
    verifier: object
    audit: object
    replay: object
    clock: Callable[[], datetime] = _utc_now
    operation_id_factory: Callable[[], str] = _identifier
    event_id_factory: Callable[[], str] = _identifier

    def execute(self, command):
        now = self.clock()
        authorized, rejection = authorize_action_execution(
            self.lifecycle, self.provider, self.permissions, command, now,
        )
        operation_id = self.operation_id_factory()
        if rejection is not None:
            return _rejected(command.plan_instance_id, operation_id, rejection)
        requested = self._requested(command, authorized, operation_id, now)
        if requested is None:
            return _rejected(
                command.plan_instance_id, operation_id,
                ActionExecutionRejection.AUDIT_UNAVAILABLE,
            )
        preconditions = evaluate_conditions(
            self.verifier, command.proposal.preconditions, command.proposal,
        )
        if any(not item.passed for item in preconditions):
            result = precondition_result(command.proposal, preconditions, self.clock())
            return self._finish(
                command, authorized, operation_id, requested, preconditions,
                result, provider_invoked=False,
            )
        if not self.replay.reserve(command.confirmation.confirmation_id):
            terminal = self._record_replay(command, authorized, operation_id)
            audit_ids = (requested.intent.event_id,)
            if terminal is not None:
                audit_ids += (terminal.intent.event_id,)
            return _rejected(
                command.plan_instance_id, operation_id,
                ActionExecutionRejection.REPLAYED, audit_ids,
            )
        result = self._invoke(command)
        return self._finish(
            command, authorized, operation_id, requested, preconditions,
            result, provider_invoked=True,
        )

    def _requested(self, command, authorized, operation_id, now):
        intent = requested_audit(
            command, authorized, operation_id, self.event_id_factory(), now,
        )
        try:
            return self.audit.append(intent)
        except Exception:
            return None

    def _invoke(self, command):
        try:
            provider_result = self.provider.execute_action(
                command.proposal, command.confirmation,
            )
        except Exception:
            return provider_failure_result(command.proposal, self.clock())
        return finalize_provider_result(
            command.proposal, provider_result, self.verifier, self.clock(),
        )

    def _finish(
        self, command, authorized, operation_id, requested, preconditions,
        result, provider_invoked,
    ):
        condition_ids = tuple(item.condition_id for item in preconditions)
        if provider_invoked:
            condition_ids += tuple(item.condition_id for item in result.postcondition_evidence)
        condition_ids = tuple(dict.fromkeys(condition_ids))
        terminal = self._terminal(
            command, authorized, operation_id, result, condition_ids,
        )
        recovery = recovery_metadata(command.proposal, result, provider_invoked)
        if terminal is None:
            return self._audit_failure(
                command, operation_id, requested, preconditions, result, recovery,
                provider_invoked,
            )
        return self._advance(
            command, operation_id, (requested, terminal), preconditions,
            result, recovery, provider_invoked,
        )

    def _terminal(self, command, authorized, operation_id, result, condition_ids):
        intent = terminal_audit(
            command, authorized, operation_id, self.event_id_factory(), self.clock(),
            result, condition_ids,
        )
        try:
            return self.audit.append(intent)
        except Exception:
            return None

    def _audit_failure(
        self, command, operation_id, requested, preconditions, source, recovery,
        provider_invoked,
    ):
        if not provider_invoked:
            return _rejected(
                command.plan_instance_id, operation_id,
                ActionExecutionRejection.AUDIT_UNAVAILABLE,
                (requested.intent.event_id,),
            )
        failed = audit_failure_result(command.proposal, source, self.clock())
        recovery = replace(
            recovery,
            compensation_required=recovery.reversal_capability_id is not None,
        )
        advanced = self._advance(
            command, operation_id, (requested,), preconditions, failed,
            recovery, True,
        )
        return ActionExecutionResult(
            command.plan_instance_id, operation_id, True,
            advanced.audit_event_ids, preconditions, failed, recovery,
            advanced.snapshot, ActionExecutionRejection.AUDIT_UNAVAILABLE,
        )

    def _advance(
        self, command, operation_id, audit_records, preconditions,
        result, recovery, provider_invoked,
    ):
        outcome = StepOutcome.SUCCEEDED if result.verified else StepOutcome.FAILED
        references = (
            PlanEvidenceReference(
                operation_id, PlanEvidenceKind.ACTION_RESULT,
                command.proposal.request.capability_id,
                command.proposal.request.permission_grant_id,
            ),
            *tuple(
                PlanEvidenceReference(
                    record.intent.event_id, PlanEvidenceKind.ACTION_AUDIT,
                    command.proposal.request.capability_id,
                    command.proposal.request.permission_grant_id,
                )
                for record in audit_records
            ),
        )
        advanced = self.lifecycle.advance(
            command.plan_instance_id, command.expected_revision, outcome, references,
        )
        event_ids = tuple(record.intent.event_id for record in audit_records)
        if advanced.rejection is not None:
            if not provider_invoked:
                return _rejected(
                    command.plan_instance_id, operation_id, advanced.rejection, event_ids,
                )
            return ActionExecutionResult(
                command.plan_instance_id, operation_id, True, event_ids,
                preconditions, result, recovery, rejection=advanced.rejection,
            )
        return ActionExecutionResult(
            command.plan_instance_id, operation_id, provider_invoked, event_ids,
            preconditions, result, recovery, advanced.snapshot,
        )

    def _record_replay(self, command, authorized, operation_id):
        result = provider_failure_result(
            command.proposal, self.clock(), "application.action_replayed"
        )
        intent = terminal_audit(
            command, authorized, operation_id, self.event_id_factory(), self.clock(),
            result, (),
        )
        try:
            return self.audit.append(intent)
        except Exception:
            return None


def _rejected(plan_id, operation_id, rejection, audit_ids=()):
    return ActionExecutionResult(
        plan_id, operation_id, False, tuple(audit_ids), rejection=rejection,
    )
