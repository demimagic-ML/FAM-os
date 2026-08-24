"""Core-owned authorization and recovery policy for candidate edits."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from pathlib import PurePosixPath
from typing import Protocol
from uuid import uuid4

from fam_os.core.engineering.authority import EngineeringAuthority, EngineeringOperation
from fam_os.core.engineering.candidate_edit import CandidateEditRecord, CandidateEditStatus
from fam_os.core.engineering.grants import (
    EngineeringAuthorizationDecision, EngineeringAuthorizationRequest,
    EngineeringResourceImpact,
)
from fam_os.core.engineering.preparation import EngineeringPreparationResult
from fam_os.core.engineering.task_definition import EngineeringTaskDefinition
from fam_os.core.engineering.transactions import (
    CandidateArtifact, CandidateOperation, CandidateOperationKind, CandidateWorkspace,
)


class CandidateEditStore(Protocol):
    def load(self, edit_id: str) -> CandidateEditRecord | None: ...
    def begin(self, record: CandidateEditRecord) -> None: ...
    def save(self, expected_revision: int, record: CandidateEditRecord) -> None: ...
    def usage(self, task_id: str) -> tuple[int, int]: ...


class CandidateEditor(Protocol):
    def stage_artifact(self, candidate: CandidateWorkspace, artifact: CandidateArtifact, content: bytes) -> None: ...
    def execute(self, candidate: CandidateWorkspace, operation: CandidateOperation, artifacts: dict[str, CandidateArtifact]) -> None: ...
    def effect_applied(self, candidate: CandidateWorkspace, operation: CandidateOperation, artifact: CandidateArtifact | None) -> tuple[bool, str | None]: ...


class EngineeringDecisionAuthorizer(Protocol):
    def authorize(self, request: EngineeringAuthorizationRequest) -> EngineeringAuthorizationDecision: ...


class CandidateEditingService:
    def __init__(self, authorizer: EngineeringDecisionAuthorizer, editor: CandidateEditor, store: CandidateEditStore, *, clock: Callable[[], datetime] | None = None, identifier: Callable[[], str] | None = None) -> None:
        self._authorizer = authorizer
        self._editor = editor
        self._store = store
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: str(uuid4()))

    def edit(self, definition: EngineeringTaskDefinition, preparation: EngineeringPreparationResult, *, edit_id: str, session_id: str, principal_id: str, operation: CandidateOperation, artifact: CandidateArtifact | None = None, content: bytes | None = None, cancelled: Callable[[], bool] = lambda: False) -> CandidateEditRecord:
        self._validate(definition, preparation, operation, artifact, content)
        existing = self._store.load(edit_id)
        if existing is not None:
            resumed = self._resume_existing(
                existing, definition, preparation, session_id, principal_id,
                operation, artifact,
            )
            if resumed is not None:
                return resumed
        changed_bytes = _changed_bytes(preparation.candidate, operation, artifact)
        self._require_budget(definition, changed_bytes, existing is not None)
        decisions = self._authorize(definition, preparation, edit_id, session_id, principal_id, operation, changed_bytes)
        now = self._clock()
        record = existing or CandidateEditRecord(
            edit_id, definition.definition_id, definition.task.task_id,
            preparation.candidate.candidate_id, session_id, principal_id,
            operation, artifact, tuple(item.decision_id for item in decisions),
            changed_bytes, CandidateEditStatus.INTENT_RECORDED, 0, now, now,
        )
        if existing is None:
            self._store.begin(record)
        if cancelled():
            return self._finish(record, CandidateEditStatus.FAILED, None, "cancelled_before_effect")
        live = self._authorize(definition, preparation, edit_id, session_id, principal_id, operation, changed_bytes)
        record = replace(
            record, authorization_decision_ids=tuple(item.decision_id for item in live),
            revision=record.revision + 1, updated_at=self._clock(),
        )
        self._store.save(record.revision - 1, record)
        try:
            if artifact is not None and content is not None:
                self._editor.stage_artifact(preparation.candidate, artifact, content)
            self._editor.execute(
                preparation.candidate, operation,
                {} if artifact is None else {artifact.artifact_id: artifact},
            )
        except Exception:
            applied, after = self._editor.effect_applied(preparation.candidate, operation, artifact)
            return self._finish(
                record,
                CandidateEditStatus.APPLIED if applied else CandidateEditStatus.RECOVERY_REQUIRED,
                after, None if applied else "effect_postcondition_uncertain",
            )
        applied, after = self._editor.effect_applied(preparation.candidate, operation, artifact)
        if not applied:
            return self._finish(record, CandidateEditStatus.RECOVERY_REQUIRED, after, "effect_postcondition_failed")
        return self._finish(record, CandidateEditStatus.APPLIED, after, None)

    def _resume_existing(self, record, definition, preparation, session_id, principal_id, operation, artifact):
        self._require_same(
            record, definition, preparation, session_id, principal_id,
            operation, artifact,
        )
        if record.status is CandidateEditStatus.APPLIED:
            return record
        if record.status is not CandidateEditStatus.INTENT_RECORDED:
            raise RuntimeError("candidate edit is not retryable")
        applied, after = self._editor.effect_applied(
            preparation.candidate, operation, artifact,
        )
        return (
            self._finish(record, CandidateEditStatus.APPLIED, after, None)
            if applied else None
        )

    def _authorize(self, definition, preparation, edit_id, session_id, principal_id, operation, changed_bytes):
        paths = (operation.path,) if operation.source_path is None else (operation.source_path, operation.path)
        decisions = []
        for path in paths:
            request = EngineeringAuthorizationRequest(
                self._identifier(), definition.task.grant_id, principal_id,
                EngineeringAuthority.MODIFY, definition.task.task_id, session_id,
                edit_id, edit_id, preparation.candidate.owner_workspace, path,
                None, None, None, None, None, None,
                EngineeringResourceImpact(0, 0, 0, 1, changed_bytes, 0),
            )
            decision = self._authorizer.authorize(request)
            if not decision.allowed or decision.request_id != request.request_id or decision.grant_id != request.grant_id or decision.authority is not request.authority:
                raise PermissionError("candidate edit lacks exact live modify authority")
            decisions.append(decision)
        return tuple(decisions)

    def _finish(self, record, status, after, failure):
        updated = replace(
            record, status=status, revision=record.revision + 1,
            updated_at=self._clock(), after_sha256=after, failure_code=failure,
        )
        self._store.save(record.revision, updated)
        return updated

    def _require_budget(self, definition, changed_bytes, retry):
        files, used_bytes = self._store.usage(definition.task.task_id)
        if not retry:
            files += 1
            used_bytes += changed_bytes
        if files > definition.task.max_changed_files or used_bytes > definition.task.max_changed_bytes:
            raise PermissionError("candidate edit exceeds durable task change budget")

    @staticmethod
    def _validate(definition, preparation, operation, artifact, content):
        task = definition.task
        if preparation.definition_id != definition.definition_id or preparation.candidate.task_id != task.task_id:
            raise ValueError("candidate edit preparation differs from durable task")
        required = _required_operation(operation.kind)
        if EngineeringAuthority.MODIFY not in task.authorities or required not in task.permitted_operations:
            raise PermissionError("candidate edit operation is outside durable task authority")
        for path in filter(None, (operation.source_path, operation.path)):
            if not _path_allowed(path, task.path_allowlist, task.path_denylist):
                raise PermissionError("candidate edit path is outside durable task scope")
        if artifact is None and content is not None:
            raise ValueError("candidate edit content requires artifact metadata")
        if artifact is not None and (content is None or len(content) != artifact.size_bytes):
            raise ValueError("candidate edit artifact content is absent or has wrong size")
        if artifact is not None and hashlib.sha256(content or b"").hexdigest() != artifact.content_sha256:
            raise ValueError("candidate edit artifact content digest is invalid")

    @staticmethod
    def _require_same(record, definition, preparation, session_id, principal_id, operation, artifact):
        if (
            record.definition_id != definition.definition_id
            or record.candidate_id != preparation.candidate.candidate_id
            or record.session_id != session_id
            or record.principal_id != principal_id
            or record.operation != operation
            or record.artifact != artifact
        ):
            raise RuntimeError("candidate edit retry differs from recorded intent")


def _required_operation(kind: CandidateOperationKind) -> EngineeringOperation:
    if kind in {CandidateOperationKind.CREATE_DIRECTORY, CandidateOperationKind.CREATE_FILE}:
        return EngineeringOperation.CREATE
    if kind in {CandidateOperationKind.PATCH_FILE, CandidateOperationKind.RESTORE, CandidateOperationKind.SET_EXECUTABLE}:
        return EngineeringOperation.REPLACE
    if kind is CandidateOperationKind.MOVE:
        return EngineeringOperation.MOVE
    return EngineeringOperation.DELETE


def _path_allowed(path: str, allowlist: tuple[str, ...], denylist: tuple[str, ...]) -> bool:
    value = PurePosixPath(path)
    return not any(value.match(item) for item in denylist) and (
        not allowlist or any(value.match(item) for item in allowlist)
    )


def _changed_bytes(candidate, operation, artifact):
    if artifact is not None:
        return artifact.size_bytes
    source = operation.source_path or operation.path
    baseline = next((item for item in candidate.entries if item.path == source), None)
    return 0 if baseline is None else baseline.size_bytes
