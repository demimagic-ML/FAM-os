"""Core policy for preview, exact approval, apply, and recovery."""

from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol

from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.candidate_changeset import (
    CandidateChangesetRecord, CandidateChangesetStatus,
    candidate_preview_digest, candidate_rollback_digest,
)
from fam_os.core.engineering.evidence import CheckpointDecision, CheckpointDisposition
from fam_os.core.engineering.grants import (
    EngineeringAuthorizationDecision, EngineeringAuthorizationRequest,
    EngineeringResourceImpact,
)
from fam_os.core.engineering.preparation import EngineeringPreparationResult
from fam_os.core.engineering.task_definition import EngineeringTaskDefinition
from fam_os.core.engineering.transactions import CandidateApplyStatus
from fam_os.core.engineering.integration_environment import (
    integration_environment_plan_digest,
)
from fam_os.core.engineering.postgresql_evidence_policy import (
    postgresql_verification_evidence_ids,
)


class ChangesetStore(Protocol):
    def begin(self, record: CandidateChangesetRecord) -> None: ...
    def save(self, expected_revision: int, record: CandidateChangesetRecord) -> None: ...


class CandidateTransactionAdapter(Protocol):
    def preview(self, candidate, transaction_id, operations, artifacts, verification_summary, *, verification_evidence_ids, now=None): ...
    def reconcile(self, candidate, preview, operations, *, approved, now=None): ...
    def recover(self, candidate, *, now=None): ...


class CandidateChangesetService:
    def __init__(self, authorizer, adapter: CandidateTransactionAdapter, store: ChangesetStore, *, clock=None, identifier=None) -> None:
        self._authorizer = authorizer
        self._adapter = adapter
        self._store = store
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: "changeset-authorization")

    def preview(
        self, definition: EngineeringTaskDefinition,
        preparation: EngineeringPreparationResult, edits, verifications,
        changeset_id: str, *, final_operations=None, final_artifacts=None,
        verification_ids=None, runtime_diagnostic_receipts=(),
        database_evidence=(), integration_environment_evidence=(),
        postgresql_evidence=(),
    ) -> CandidateChangesetRecord:
        applied = tuple(item for item in edits if item.status.value == "applied")
        selected = None if verification_ids is None else set(verification_ids)
        passed = tuple(
            item for item in verifications
            if item.passed and (
                selected is None or item.verification_id in selected
            )
        )
        if not applied:
            raise ValueError("candidate preview requires applied edits")
        operations = (
            tuple(item.operation for item in applied)
            if final_operations is None else tuple(final_operations)
        )
        paths = tuple(item.source_path or item.path for item in operations)
        if len(paths) != len(set(paths)):
            raise ValueError("candidate preview requires one final operation per source path")
        artifacts = (
            tuple(item.artifact for item in applied if item.artifact is not None)
            if final_artifacts is None else tuple(final_artifacts)
        )
        if selected is not None and {
            item.verification_id for item in passed
        } != selected:
            raise ValueError("candidate preview verification selection is incomplete")
        evidence_ids = tuple(item.evidence.evidence_id for item in passed)
        diagnostics = tuple(runtime_diagnostic_receipts)
        if any(
            item.task_id != definition.task.task_id
            or item.candidate_id != preparation.candidate.candidate_id
            or item.status.value != "passed"
            for item in diagnostics
        ):
            raise ValueError("candidate preview runtime diagnostics are not passing and exact")
        diagnostic_ids = tuple(item.receipt_id for item in diagnostics)
        if len(set(diagnostic_ids)) != len(diagnostic_ids):
            raise ValueError("candidate preview runtime diagnostics are duplicated")
        database = tuple(database_evidence)
        if any(
            plan.task_id != definition.task.task_id
            or plan.candidate_id != preparation.candidate.candidate_id
            or plan.approved_changeset_id != changeset_id
            or receipt.plan_id != plan.plan_id
            or receipt.target_id != plan.target.target_id
            or receipt.status.value != "verified"
            or receipt.applied_step_ids
            != tuple(step.step_id for step in plan.migration_steps)
            for plan, receipt in database
        ):
            raise ValueError("candidate preview database evidence is not exact")
        database_ids = tuple(receipt.receipt_id for _plan, receipt in database)
        if len(set(database_ids)) != len(database_ids):
            raise ValueError("candidate preview database evidence is duplicated")
        environments = tuple(integration_environment_evidence)
        if any(
            plan.task_id != definition.task.task_id
            or plan.candidate_id != preparation.candidate.candidate_id
            or start.environment_id != plan.environment_id
            or start.plan_sha256 != integration_environment_plan_digest(plan)
            or start.receipt.status.value != "ready"
            or cleanup.environment_id != plan.environment_id
            or cleanup.permit_id != start.permit.permit_id
            or cleanup.status.value != "cleaned"
            or cleanup.services != start.receipt.services
            or not cleanup.cleanup_evidence_ids
            for plan, start, cleanup in environments
        ):
            raise ValueError("candidate preview integration evidence is not exact")
        environment_ids = tuple(
            cleanup.receipt_id for _plan, _start, cleanup in environments
        )
        if len(set(environment_ids)) != len(environment_ids):
            raise ValueError("candidate preview integration evidence is duplicated")
        postgresql_ids = postgresql_verification_evidence_ids(
            definition, preparation, changeset_id, postgresql_evidence,
            environments,
        )
        if not passed and not database and not environments and not postgresql_ids:
            raise ValueError(
                "candidate preview requires trusted passing verification evidence"
            )
        now = self._clock()
        preview = self._adapter.preview(
            preparation.candidate, changeset_id, operations,
            {item.artifact_id: item for item in artifacts},
            f"{len(passed)} signed candidate verification run(s) and "
            f"{len(diagnostics)} runtime diagnostic run(s) and "
            f"{len(database)} database lifecycle(s) and "
            f"{len(environments)} integration environment(s) and "
            f"{len(postgresql_ids)} PostgreSQL lifecycle(s) passed",
            verification_evidence_ids=(
                *evidence_ids, *diagnostic_ids, *database_ids,
                *environment_ids, *postgresql_ids,
            ),
            now=now,
        )
        record = CandidateChangesetRecord(
            changeset_id, definition.definition_id, definition.task.task_id,
            preparation.candidate.candidate_id, preview, operations, artifacts,
            (), CandidateChangesetStatus.PREVIEWED, 0, now, now,
        )
        self._store.begin(record)
        return record

    def apply(self, definition: EngineeringTaskDefinition, preparation: EngineeringPreparationResult, record: CandidateChangesetRecord, decision: CheckpointDecision, *, session_id: str, principal_id: str) -> CandidateChangesetRecord:
        self._validate_decision(definition, preparation, record, decision)
        first = self._authorize(definition, preparation, record, session_id, principal_id)
        intent = replace(
            record, decision=decision, status=CandidateChangesetStatus.APPLY_INTENT,
            effect_authorization_decision_ids=tuple(item.decision_id for item in first),
            revision=record.revision + 1, updated_at=self._clock(),
        )
        self._store.save(record.revision, intent)
        live = self._authorize(definition, preparation, intent, session_id, principal_id)
        intent = replace(
            intent, effect_authorization_decision_ids=tuple(item.decision_id for item in live),
            revision=intent.revision + 1, updated_at=self._clock(),
        )
        self._store.save(intent.revision - 1, intent)
        receipt = self._adapter.reconcile(
            preparation.candidate, record.preview, record.operations,
            approved=True, now=self._clock(),
        )
        status = {
            CandidateApplyStatus.APPLIED: CandidateChangesetStatus.APPLIED,
            CandidateApplyStatus.ROLLED_BACK: CandidateChangesetStatus.ROLLED_BACK,
            CandidateApplyStatus.RECOVERY_REQUIRED: CandidateChangesetStatus.RECOVERY_REQUIRED,
        }[receipt.status]
        completed = replace(
            intent, status=status, receipt=receipt,
            revision=intent.revision + 1, updated_at=self._clock(),
            failure_code=None if status is CandidateChangesetStatus.APPLIED else "candidate_apply_failed",
        )
        self._store.save(intent.revision, completed)
        return completed

    def recover(self, preparation, record):
        if record.status is not CandidateChangesetStatus.APPLY_INTENT:
            return record
        try:
            receipt = self._adapter.recover(preparation.candidate, now=self._clock())
        except FileNotFoundError:
            raise RuntimeError("candidate apply intent has no recovery journal")
        status = (
            CandidateChangesetStatus.ROLLED_BACK
            if receipt.status is CandidateApplyStatus.ROLLED_BACK
            else CandidateChangesetStatus.RECOVERY_REQUIRED
        )
        recovered = replace(
            record, status=status, receipt=receipt,
            revision=record.revision + 1, updated_at=self._clock(),
            failure_code="interrupted_apply_recovered",
        )
        self._store.save(record.revision, recovered)
        return recovered

    def rollback(
        self, definition: EngineeringTaskDefinition,
        preparation: EngineeringPreparationResult,
        record: CandidateChangesetRecord,
        decision: CheckpointDecision,
        expected_head_object_id: str,
        *, session_id: str, principal_id: str,
    ) -> CandidateChangesetRecord:
        """Restore a successful apply after a separately approved rollback intent."""
        if record.status is CandidateChangesetStatus.EXPLICITLY_ROLLED_BACK:
            self._validate_rollback_decision(
                definition, preparation, record, decision,
                expected_head_object_id,
            )
            return record
        if record.status is CandidateChangesetStatus.ROLLBACK_INTENT:
            self._validate_rollback_decision(
                definition, preparation, record, decision,
                expected_head_object_id,
            )
            return self._finish_rollback(
                definition, preparation, record,
                session_id=session_id, principal_id=principal_id,
            )
        self._validate_rollback_decision(
            definition, preparation, record, decision,
            expected_head_object_id,
        )
        first = self._authorize(
            definition, preparation, record, session_id, principal_id,
        )
        intent = replace(
            record,
            status=CandidateChangesetStatus.ROLLBACK_INTENT,
            rollback_decision=decision,
            rollback_authorization_decision_ids=tuple(
                item.decision_id for item in first
            ),
            revision=record.revision + 1,
            updated_at=self._clock(),
        )
        self._store.save(record.revision, intent)
        return self._finish_rollback(
            definition, preparation, intent,
            session_id=session_id, principal_id=principal_id,
        )

    def _finish_rollback(
        self, definition, preparation, record, *, session_id, principal_id,
    ):
        live = self._authorize(
            definition, preparation, record, session_id, principal_id,
        )
        intent = replace(
            record,
            rollback_authorization_decision_ids=(
                *record.rollback_authorization_decision_ids,
                *(item.decision_id for item in live),
            ),
            revision=record.revision + 1,
            updated_at=self._clock(),
        )
        self._store.save(record.revision, intent)
        receipt = self._adapter.recover(
            preparation.candidate, now=self._clock(),
        )
        status = (
            CandidateChangesetStatus.EXPLICITLY_ROLLED_BACK
            if receipt.status is CandidateApplyStatus.ROLLED_BACK
            and receipt.rollback_complete
            else CandidateChangesetStatus.ROLLBACK_RECOVERY_REQUIRED
        )
        completed = replace(
            intent,
            status=status,
            rollback_receipt=receipt,
            revision=intent.revision + 1,
            updated_at=self._clock(),
            failure_code=(
                None if status is CandidateChangesetStatus.EXPLICITLY_ROLLED_BACK
                else "explicit_rollback_incomplete"
            ),
        )
        self._store.save(intent.revision, completed)
        return completed

    def _authorize(self, definition, preparation, record, session_id, principal_id):
        impact = EngineeringResourceImpact(
            0, 0, 0, len(record.preview.items),
            sum(abs(item.size_delta_bytes) for item in record.preview.items), 0,
        )
        decisions = []
        paths = sorted({item.path for item in record.preview.items})
        for path in paths:
            request = EngineeringAuthorizationRequest(
                self._identifier(), definition.task.grant_id, principal_id,
                EngineeringAuthority.MODIFY, definition.task.task_id, session_id,
                None, record.changeset_id, preparation.candidate.owner_workspace,
                path, None, None, None, None, None, None, impact,
            )
            decision = self._authorizer.authorize(request)
            if not decision.allowed or decision.request_id != request.request_id or decision.grant_id != request.grant_id or decision.authority is not request.authority:
                raise PermissionError("candidate apply lacks exact live modify authority")
            decisions.append(decision)
        return tuple(decisions)

    @staticmethod
    def _validate_decision(definition, preparation, record, decision):
        if (
            record.definition_id != definition.definition_id
            or record.candidate_id != preparation.candidate.candidate_id
            or decision.task_id != definition.task.task_id
            or decision.proposal_id != record.changeset_id
            or decision.checkpoint_id != record.changeset_id
            or decision.decided_by != definition.task.owner_id
            or decision.disposition is not CheckpointDisposition.APPROVED
            or decision.proposal_sha256 != candidate_preview_digest(record.preview)
        ):
            raise PermissionError("candidate apply decision is not exact")

    @staticmethod
    def _validate_rollback_decision(
        definition, preparation, record, decision, expected_head_object_id,
    ):
        rollback_id = f"rollback-{record.changeset_id}"
        if (
            record.definition_id != definition.definition_id
            or record.candidate_id != preparation.candidate.candidate_id
            or record.status
            not in {
                CandidateChangesetStatus.APPLIED,
                CandidateChangesetStatus.ROLLBACK_INTENT,
                CandidateChangesetStatus.EXPLICITLY_ROLLED_BACK,
            }
            or decision.task_id != definition.task.task_id
            or decision.proposal_id != rollback_id
            or decision.checkpoint_id != rollback_id
            or decision.decided_by != definition.task.owner_id
            or decision.disposition is not CheckpointDisposition.APPROVED
            or decision.proposal_sha256
            != candidate_rollback_digest(record, expected_head_object_id)
        ):
            raise PermissionError("candidate rollback decision is not exact")
        if (
            record.rollback_decision is not None
            and record.rollback_decision != decision
        ):
            raise PermissionError("candidate rollback retry changed its decision")
