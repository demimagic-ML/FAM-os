"""Product facade for isolated candidate editing and signed verification."""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.filesystem import CandidateWorkspaceAdapter
from fam_os.core.engineering import (
    CandidateArtifact, CandidateEditingService, CandidateOperation,
    CandidateChangesetService, CandidateChangesetStatus,
    CheckpointDecision,
    CandidateVerificationService, CandidateVerificationStatus,
    EngineeringLoopStage, EngineeringSandboxProfile, SandboxNetworkMode,
    squash_candidate_edits,
)


class ProductCandidateEngineeringApi:
    def __init__(self, store, preparations, candidate_root: Path, authorizer, edits, verification_service: CandidateVerificationService | None, verifications, changesets, lifecycle, require_owner, validate_grant) -> None:
        self._store = store
        self._preparations = preparations
        self._candidate_root = candidate_root
        self._authorizer = authorizer
        self._edits = edits
        self._verification_service = verification_service
        self._verifications = verifications
        self._changesets = changesets
        self._lifecycle = lifecycle
        self._require_owner = require_owner
        self._validate_grant = validate_grant

    def edit(self, owner_id: str, task_id: str, *, edit_id: str, session_id: str, principal_id: str, operation: CandidateOperation, artifact: CandidateArtifact | None = None, content: bytes | None = None):
        self._require_owner(owner_id)
        if self._authorizer is None or self._edits is None:
            raise RuntimeError("candidate editing was not composed")
        definition, preparation, state = self._prepared(task_id)
        if state.stage is not EngineeringLoopStage.CANDIDATE_READY:
            raise PermissionError("candidate edits require the pre-verification candidate stage")
        self._validate_grant(
            task_id, definition.task.grant_id, datetime.now(timezone.utc),
        )
        editor = CandidateWorkspaceAdapter(
            Path(preparation.candidate.owner_workspace), self._candidate_root,
        )
        return CandidateEditingService(
            self._authorizer, editor, self._edits,
        ).edit(
            definition, preparation, edit_id=edit_id, session_id=session_id,
            principal_id=principal_id, operation=operation,
            artifact=artifact, content=content,
        )

    def edits(self, owner_id: str, task_id: str):
        self._require_owner(owner_id)
        if self._edits is None:
            raise RuntimeError("candidate editing was not composed")
        return self._edits.for_task(task_id)

    def verify(self, owner_id: str, task_id: str, *, verification_id: str, session_id: str, principal_id: str, toolchain: str, recipe_id: str, recipe_version: str, additional_budget=None, record_lifecycle: bool = True):
        self._require_owner(owner_id)
        if self._verification_service is None or self._verifications is None:
            raise RuntimeError("candidate verification was not composed")
        definition, preparation, state = self._prepared(task_id)
        existing = self._verifications.load(verification_id)
        if existing is not None:
            return self._reconcile(
                existing, definition, preparation, state, additional_budget,
                record_lifecycle,
            )
        if state.stage not in {
            EngineeringLoopStage.CANDIDATE_READY, EngineeringLoopStage.VERIFIED,
        }:
            raise PermissionError("candidate verification requires candidate-ready state")
        self._validate_grant(
            task_id, definition.task.grant_id, datetime.now(timezone.utc),
        )
        profile = _profile(definition, verification_id)
        record = self._verification_service.verify(
            definition, preparation, verification_id=verification_id,
            session_id=session_id, principal_id=principal_id,
            toolchain=toolchain, recipe_id=recipe_id,
            recipe_version=recipe_version, profile=profile,
        )
        if (
            record_lifecycle
            and record.status is CandidateVerificationStatus.COMPLETED
            and record.passed
        ):
            self._lifecycle.record_verification(
                record.evidence, additional_budget=additional_budget,
            )
        return record

    def verifications(self, owner_id: str, task_id: str):
        self._require_owner(owner_id)
        if self._verifications is None:
            raise RuntimeError("candidate verification was not composed")
        return self._verifications.for_task(task_id)

    def reverify(self, owner_id: str, task_id: str, *, verification_id: str, session_id: str, principal_id: str, toolchain: str, recipe_id: str, recipe_version: str, record_lifecycle: bool = True):
        self._require_owner(owner_id)
        if self._verification_service is None or self._verifications is None:
            raise RuntimeError("candidate verification was not composed")
        definition, preparation, state = self._prepared(task_id)
        existing = self._verifications.load(verification_id)
        if existing is not None:
            return self._reconcile_postapply(
                existing, definition, state, record_lifecycle,
            )
        if state.stage not in {
            EngineeringLoopStage.APPLIED, EngineeringLoopStage.REVERIFIED,
        }:
            raise PermissionError("post-apply verification requires applied state")
        self._validate_grant(task_id, definition.task.grant_id, datetime.now(timezone.utc))
        observer = CandidateWorkspaceAdapter(
            Path(preparation.candidate.owner_workspace), self._candidate_root,
        )
        observed = replace(
            preparation, candidate=observer.create(task_id),
        )
        record = self._verification_service.verify(
            definition, observed, verification_id=verification_id,
            session_id=session_id, principal_id=principal_id,
            toolchain=toolchain, recipe_id=recipe_id,
            recipe_version=recipe_version,
            profile=_profile(definition, verification_id),
        )
        if (
            record_lifecycle
            and record.status is CandidateVerificationStatus.COMPLETED
            and record.passed
        ):
            self._lifecycle.record_reverification(record.evidence)
        return record

    def preview(
        self, owner_id: str, task_id: str, changeset_id: str, *,
        verification_ids=None, runtime_diagnostic_receipts=(),
        database_evidence=(), integration_environment_evidence=(),
        postgresql_evidence=(),
    ):
        self._require_owner(owner_id)
        if self._changesets is None or self._edits is None or self._verifications is None:
            raise RuntimeError("candidate changesets were not composed")
        definition, preparation, state = self._prepared(task_id)
        existing = self._changesets.load(changeset_id)
        if existing is not None:
            return self._reconcile_preview(existing, state)
        if state.stage is not EngineeringLoopStage.VERIFIED:
            raise PermissionError("candidate preview requires verified state")
        self._validate_grant(task_id, definition.task.grant_id, datetime.now(timezone.utc))
        service = self._changeset_service(preparation)
        edits = self._edits.for_task(task_id)
        adapter = CandidateWorkspaceAdapter(
            Path(preparation.candidate.owner_workspace), self._candidate_root,
        )
        operations, artifacts = squash_candidate_edits(
            task_id, preparation.candidate,
            adapter.current_entries(preparation.candidate), edits,
            maximum_operations=definition.task.max_changed_files,
            maximum_content_bytes=definition.task.max_changed_bytes,
            authorized_external_paths=tuple(
                plan.target.database_name for plan, _receipt in database_evidence
            ),
        )
        record = service.preview(
            definition, preparation, edits,
            self._verifications.for_task(task_id), changeset_id,
            final_operations=operations, final_artifacts=artifacts,
            verification_ids=verification_ids,
            runtime_diagnostic_receipts=runtime_diagnostic_receipts,
            database_evidence=database_evidence,
            integration_environment_evidence=integration_environment_evidence,
            postgresql_evidence=postgresql_evidence,
        )
        self._lifecycle.request_changeset_checkpoint(task_id, record.preview)
        return record

    def current_candidate(self, owner_id: str, task_id: str):
        self._require_owner(owner_id)
        definition, preparation, _state = self._prepared(task_id)
        self._validate_grant(
            task_id, definition.task.grant_id, datetime.now(timezone.utc),
        )
        adapter = CandidateWorkspaceAdapter(
            Path(preparation.candidate.owner_workspace), self._candidate_root,
        )
        return replace(
            preparation.candidate,
            entries=adapter.current_entries(preparation.candidate),
        )

    def apply(self, owner_id: str, task_id: str, changeset_id: str, decision: CheckpointDecision, *, session_id: str, principal_id: str):
        self._require_owner(owner_id)
        if self._changesets is None:
            raise RuntimeError("candidate changesets were not composed")
        definition, preparation, state = self._prepared(task_id)
        record = self._changesets.load(changeset_id)
        if record is None:
            raise KeyError("candidate changeset is unavailable")
        service = self._changeset_service(preparation)
        if record.status is CandidateChangesetStatus.APPLY_INTENT:
            return service.recover(preparation, record)
        if record.status is CandidateChangesetStatus.APPLIED:
            if state.stage is EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED:
                self._lifecycle.record_apply(task_id, record.receipt, record.decision)
            return record
        if state.stage is not EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED:
            raise PermissionError("candidate apply requires a pending changeset checkpoint")
        self._validate_grant(task_id, definition.task.grant_id, datetime.now(timezone.utc))
        result = service.apply(
            definition, preparation, record, decision,
            session_id=session_id, principal_id=principal_id,
        )
        if result.status is CandidateChangesetStatus.APPLIED:
            self._lifecycle.record_apply(task_id, result.receipt, decision)
        return result

    def changesets(self, owner_id: str, task_id: str):
        self._require_owner(owner_id)
        if self._changesets is None:
            raise RuntimeError("candidate changesets were not composed")
        return self._changesets.for_task(task_id)

    def rollback(
        self, owner_id: str, task_id: str, changeset_id: str,
        decision: CheckpointDecision, expected_head_object_id: str,
        *, session_id: str, principal_id: str,
    ):
        self._require_owner(owner_id)
        if self._changesets is None:
            raise RuntimeError("candidate changesets were not composed")
        definition, preparation, state = self._prepared(task_id)
        record = self._changesets.load(changeset_id)
        if record is None:
            raise KeyError("candidate changeset is unavailable")
        if state.stage not in {
            EngineeringLoopStage.APPLIED,
            EngineeringLoopStage.COMMITTED,
            EngineeringLoopStage.ROLLED_BACK,
        }:
            raise PermissionError("explicit rollback requires applied state")
        self._validate_grant(
            task_id, definition.task.grant_id, datetime.now(timezone.utc),
        )
        return self._changeset_service(preparation).rollback(
            definition, preparation, record, decision,
            expected_head_object_id,
            session_id=session_id, principal_id=principal_id,
        )

    def close(self) -> None:
        if self._changesets is not None:
            self._changesets.close()
        if self._verifications is not None:
            self._verifications.close()
        if self._edits is not None:
            self._edits.close()

    def _prepared(self, task_id):
        values = (
            self._store.load_task(task_id), self._preparations.load(task_id),
            self._store.load(task_id),
        )
        if any(value is None for value in values):
            raise KeyError("prepared engineering task is unavailable")
        return values

    def _reconcile(
        self, record, definition, preparation, state, additional_budget=None,
        record_lifecycle=True,
    ):
        if (
            record.definition_id != definition.definition_id
            or record.candidate_id != preparation.candidate.candidate_id
            or record.task_id != definition.task.task_id
        ):
            raise RuntimeError("candidate verification retry identity differs")
        if record.status is not CandidateVerificationStatus.COMPLETED or not record.passed:
            return record
        if not record_lifecycle:
            return record
        if state.stage is EngineeringLoopStage.CANDIDATE_READY:
            self._lifecycle.record_verification(
                record.evidence, additional_budget=additional_budget,
            )
        elif record.evidence.evidence_id not in state.verification_receipt_ids:
            raise RuntimeError("candidate verification lifecycle reconciliation conflicts")
        return record

    def _reconcile_preview(self, record, state):
        if state.candidate_id != record.candidate_id:
            raise RuntimeError("candidate changeset retry identity differs")
        if state.stage is EngineeringLoopStage.VERIFIED:
            self._lifecycle.request_changeset_checkpoint(record.task_id, record.preview)
        elif (
            state.stage is not EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED
            or state.pending_changeset_id != record.changeset_id
        ):
            raise RuntimeError("candidate changeset lifecycle reconciliation conflicts")
        return record

    def _reconcile_postapply(
        self, record, definition, state, record_lifecycle=True,
    ):
        if record.definition_id != definition.definition_id or record.task_id != definition.task.task_id:
            raise RuntimeError("post-apply verification retry identity differs")
        if record.status is not CandidateVerificationStatus.COMPLETED or not record.passed:
            return record
        if not record_lifecycle:
            return record
        if state.stage in {
            EngineeringLoopStage.APPLIED, EngineeringLoopStage.REVERIFIED,
        }:
            self._lifecycle.record_reverification(record.evidence)
        elif record.evidence.evidence_id not in state.verification_receipt_ids:
            raise RuntimeError("post-apply verification lifecycle reconciliation conflicts")
        return record

    def _changeset_service(self, preparation):
        adapter = CandidateWorkspaceAdapter(
            Path(preparation.candidate.owner_workspace), self._candidate_root,
        )
        return CandidateChangesetService(
            self._authorizer, adapter, self._changesets,
        )


def _profile(definition, verification_id):
    wall = min(definition.task.max_wall_seconds, 300)
    if wall <= 0:
        raise PermissionError("candidate verification has no wall-time budget")
    return EngineeringSandboxProfile(
        f"profile-{verification_id}", 512 * 1024**2, min(wall, 60), wall,
        32, 1_048_576, 32 * 1024**2, SandboxNetworkMode.DENIED, (),
        (("PATH", "/usr/bin:/bin"),),
    )
