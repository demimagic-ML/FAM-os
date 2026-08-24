"""Replay-safe local Git delivery over exact approved changesets."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import re
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fam_os.core.engineering._validation import aware, text, texts
from fam_os.core.engineering.authority import EngineeringAuthority, EngineeringOperation
from fam_os.core.engineering.candidate_changeset import (
    CandidateChangesetRecord, CandidateChangesetStatus,
    candidate_rollback_digest,
)
from fam_os.core.engineering.transactions import CandidateOperationKind
from fam_os.core.engineering.git_delivery import (
    GitLocalAction, GitLocalActionKind, GitLocalActionReceipt,
)
from fam_os.core.engineering.grants import (
    EngineeringAuthorizationRequest, EngineeringResourceImpact,
)
from fam_os.core.engineering.task_definition import EngineeringTaskDefinition
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class LocalGitDeliveryStatus(StrEnum):
    INTENT_RECORDED = "intent_recorded"
    STAGED = "staged"
    COMMITTED = "committed"


@dataclass(frozen=True, slots=True)
class LocalGitDeliveryRecord:
    delivery_id: str
    task_id: str
    changeset_id: str
    stage_action: GitLocalAction
    commit_action: GitLocalAction
    status: LocalGitDeliveryStatus
    authorization_decision_ids: tuple[str, ...]
    revision: int
    created_at: datetime
    updated_at: datetime
    stage_receipt: GitLocalActionReceipt | None = None
    commit_receipt: GitLocalActionReceipt | None = None
    branch_action: GitLocalAction | None = None
    branch_receipt: GitLocalActionReceipt | None = None
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("delivery_id", "task_id", "changeset_id"):
            text(getattr(self, name), name)
        texts(self.authorization_decision_ids, "Git authorization decisions")
        aware(self.created_at, "created_at")
        aware(self.updated_at, "updated_at")
        if (
            self.stage_action.task_id != self.task_id
            or self.commit_action.task_id != self.task_id
            or self.stage_action.approved_change_set_id != self.changeset_id
            or self.commit_action.approved_change_set_id != self.changeset_id
        ):
            raise ValueError("local Git delivery identities are mismatched")
        if self.status is not LocalGitDeliveryStatus.INTENT_RECORDED and self.stage_receipt is None:
            raise ValueError("local Git staged state requires a receipt")
        if self.status is LocalGitDeliveryStatus.COMMITTED and self.commit_receipt is None:
            raise ValueError("local Git committed state requires a receipt")
        if self.branch_action is None:
            if self.branch_receipt is not None:
                raise ValueError("local Git branch receipt lacks an action")
        elif (
            self.branch_action.kind is not GitLocalActionKind.CREATE_BRANCH
            or self.branch_action.task_id != self.task_id
            or self.branch_action.approved_change_set_id != self.changeset_id
            or (
                self.branch_receipt is not None
                and self.branch_receipt.action_id != self.branch_action.action_id
            )
            or (
                self.status is not LocalGitDeliveryStatus.INTENT_RECORDED
                and self.branch_receipt is None
            )
        ):
            raise ValueError("local Git branch state is inconsistent")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("local Git delivery version is unsupported")


class LocalGitDeliveryStore(Protocol):
    def load(self, delivery_id: str) -> LocalGitDeliveryRecord | None: ...
    def begin(self, record: LocalGitDeliveryRecord) -> None: ...
    def save(self, expected_revision: int, record: LocalGitDeliveryRecord) -> None: ...


class LocalGitPort(Protocol):
    def observe(self, task_id: str, root): ...
    def staged_paths(self, root) -> tuple[str, ...]: ...
    def apply(self, action: GitLocalAction) -> GitLocalActionReceipt: ...
    def reconcile_commit(self, action, expected_paths) -> GitLocalActionReceipt: ...
    def reconcile_branch(self, action) -> GitLocalActionReceipt: ...
    def publication_state(
        self, task_id, root, remote_name, expected_before_object_id,
        expected_after_object_id,
    ): ...


class LocalGitDeliveryService:
    def __init__(self, authorizer, adapter: LocalGitPort, store: LocalGitDeliveryStore, *, clock=None) -> None:
        self._authorizer = authorizer
        self._adapter = adapter
        self._store = store
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def close(self) -> None:
        close = getattr(self._store, "close", None)
        if close is not None:
            close()

    def commit(
        self, definition: EngineeringTaskDefinition,
        changeset: CandidateChangesetRecord, *, session_id: str,
        principal_id: str, verification_evidence_ids: tuple[str, ...],
        message: str,
    ) -> LocalGitDeliveryRecord:
        self._validate(definition, changeset, verification_evidence_ids)
        delivery_id = f"git-delivery-{changeset.changeset_id}"
        record = self._store.load(delivery_id)
        if record is None:
            record = self._begin(
                delivery_id, definition, changeset, session_id, principal_id,
                verification_evidence_ids, message,
            )
        self._same(record, definition, changeset, verification_evidence_ids, message)
        if (
            record.status is LocalGitDeliveryStatus.INTENT_RECORDED
            and record.branch_action is not None
            and record.branch_receipt is None
        ):
            record = self._branch(record, definition, session_id, principal_id)
        if record.status is LocalGitDeliveryStatus.INTENT_RECORDED:
            record = self._stage(record, definition, session_id, principal_id)
        if record.status is LocalGitDeliveryStatus.STAGED:
            record = self._commit(record, definition, session_id, principal_id)
        return record

    def rollback_preview(
        self, definition: EngineeringTaskDefinition,
        changeset: CandidateChangesetRecord,
    ) -> dict:
        """Return the exact current rollback checkpoint without changing Git."""
        original = self._require_original_delivery(definition, changeset)
        rollback_id = f"rollback-{changeset.changeset_id}"
        persisted = self._store.load(f"git-delivery-{rollback_id}")
        expected_head = original.commit_receipt.after_object_id
        if persisted is None:
            observation = self._adapter.observe(
                definition.task.task_id,
                Path(definition.task.workspace_roots[0]),
            )
            if observation.head_object_id != expected_head:
                raise RuntimeError("local Git head changed after FAM delivery")
            if self._adapter.staged_paths(definition.task.workspace_roots[0]):
                raise PermissionError("rollback requires an empty staging area")
        else:
            if (
                persisted.task_id != definition.task.task_id
                or persisted.changeset_id != rollback_id
                or persisted.commit_action.expected_head_object_id != expected_head
            ):
                raise RuntimeError("persisted local Git rollback identity differs")
        return {
            "rollback_id": rollback_id,
            "task_id": definition.task.task_id,
            "changeset_id": changeset.changeset_id,
            "expected_head_object_id": expected_head,
            "paths": list(changeset.receipt.applied_paths),
            "approval_sha256": candidate_rollback_digest(
                changeset, expected_head,
            ),
            "consequences": [
                "Restore only FAM-owned paths whose applied state is unchanged.",
                "Create a separate local rollback commit; do not rewrite history.",
                "Preserve unrelated owner work and stop on path or Git drift.",
            ],
        }

    def precommit_rollback_preview(
        self, definition: EngineeringTaskDefinition,
        changeset: CandidateChangesetRecord,
    ) -> dict:
        """Bind rollback of an applied but uncommitted workspace changeset."""
        self._validate_precommit_rollback(definition, changeset)
        observation = self._adapter.observe(
            definition.task.task_id,
            Path(definition.task.workspace_roots[0]),
        )
        self.require_precommit_rollback_head(
            definition, changeset, observation.head_object_id,
        )
        rollback_id = f"rollback-{changeset.changeset_id}"
        return {
            "rollback_id": rollback_id,
            "task_id": definition.task.task_id,
            "changeset_id": changeset.changeset_id,
            "expected_head_object_id": observation.head_object_id,
            "paths": list(changeset.receipt.applied_paths),
            "approval_sha256": candidate_rollback_digest(
                changeset, observation.head_object_id,
            ),
            "consequences": [
                "Restore only FAM-owned paths whose applied state is unchanged.",
                "Do not create or rewrite a Git commit.",
                "Preserve unrelated owner work and stop on path or Git drift.",
            ],
        }

    def has_committed_delivery(
        self, definition: EngineeringTaskDefinition,
        changeset: CandidateChangesetRecord,
    ) -> bool:
        record = self._store.load(f"git-delivery-{changeset.changeset_id}")
        return bool(
            record is not None
            and record.task_id == definition.task.task_id
            and record.changeset_id == changeset.changeset_id
            and record.status is LocalGitDeliveryStatus.COMMITTED
            and record.commit_receipt is not None
        )

    def require_precommit_rollback_head(
        self, definition: EngineeringTaskDefinition,
        changeset: CandidateChangesetRecord,
        expected_head_object_id: str,
    ) -> None:
        """Revalidate the exact uncommitted rollback Git boundary."""
        self._validate_precommit_rollback(definition, changeset)
        observation = self._adapter.observe(
            definition.task.task_id,
            Path(definition.task.workspace_roots[0]),
        )
        if observation.head_object_id != expected_head_object_id:
            raise RuntimeError("local Git head changed before pre-commit rollback")
        if self._adapter.staged_paths(definition.task.workspace_roots[0]):
            raise PermissionError("pre-commit rollback requires an empty staging area")

    def publication_state(
        self, definition: EngineeringTaskDefinition, changeset_id: str,
        remote_name: str,
    ):
        """Return exact local publication inputs for this FAM-owned commit."""
        record = self._store.load(f"git-delivery-{changeset_id}")
        if (
            record is None
            or record.task_id != definition.task.task_id
            or record.status is not LocalGitDeliveryStatus.COMMITTED
            or record.commit_receipt is None
            or record.commit_receipt.after_object_id is None
        ):
            raise PermissionError("publication requires the exact local Git delivery")
        return self._adapter.publication_state(
            definition.task.task_id, definition.task.workspace_roots[0],
            remote_name, record.commit_receipt.before_object_id,
            record.commit_receipt.after_object_id,
        )

    def rollback(
        self, definition: EngineeringTaskDefinition,
        changeset: CandidateChangesetRecord,
        *, session_id: str, principal_id: str, message: str,
    ) -> LocalGitDeliveryRecord:
        """Commit an exact completed candidate rollback without rewriting history."""
        original = self._require_original_delivery(definition, changeset)
        self._validate_rollback(definition, changeset)
        rollback_id = f"rollback-{changeset.changeset_id}"
        delivery_id = f"git-delivery-{rollback_id}"
        evidence = (
            f"candidate-rollback:{changeset.rollback_receipt.journal_sha256}",
        )
        record = self._store.load(delivery_id)
        if record is None:
            record = self._begin_rollback(
                delivery_id, rollback_id, definition, changeset, original,
                session_id, principal_id, evidence, message,
            )
        self._same_values(
            record, definition, rollback_id, evidence, message,
        )
        if record.status is LocalGitDeliveryStatus.INTENT_RECORDED:
            record = self._stage(record, definition, session_id, principal_id)
        if record.status is LocalGitDeliveryStatus.STAGED:
            record = self._commit(record, definition, session_id, principal_id)
        return record

    def _begin(self, delivery_id, definition, changeset, session_id, principal_id, evidence, message):
        task = definition.task
        root = task.workspace_roots[0]
        observation = self._adapter.observe(task.task_id, Path(root))
        if self._adapter.staged_paths(root):
            raise PermissionError("local Git delivery requires an empty staging area")
        paths = _git_stage_paths(changeset)
        now = self._clock()
        branch = None
        if _protected_branch(observation.head_ref):
            branch = GitLocalAction(
                f"branch-{delivery_id}", task.task_id, root,
                GitLocalActionKind.CREATE_BRANCH, _feature_branch(task.task_id),
                (), None, changeset.changeset_id, evidence,
                observation.head_object_id, now,
            )
        stage = GitLocalAction(
            f"stage-{delivery_id}", task.task_id, root,
            GitLocalActionKind.STAGE_PATHS, None, paths, None,
            changeset.changeset_id, evidence, observation.head_object_id, now,
        )
        commit = GitLocalAction(
            f"commit-{delivery_id}", task.task_id, root,
            GitLocalActionKind.COMMIT, None, (), message,
            changeset.changeset_id, evidence, observation.head_object_id, now,
        )
        decision = self._authorize(
            definition, changeset, session_id, principal_id, stage.action_id,
        )
        record = LocalGitDeliveryRecord(
            delivery_id, task.task_id, changeset.changeset_id, stage, commit,
            LocalGitDeliveryStatus.INTENT_RECORDED, (decision.decision_id,),
            0, now, now, branch_action=branch,
        )
        self._store.begin(record)
        return record

    def _branch(self, record, definition, session_id, principal_id):
        action = record.branch_action
        decision = self._authorize(
            definition, None, session_id, principal_id, action.action_id,
            changeset_id=record.changeset_id,
        )
        observation = self._adapter.observe(
            record.task_id, Path(action.repository_root),
        )
        if observation.head_ref == action.branch_name:
            receipt = self._adapter.reconcile_branch(action)
        else:
            if (
                observation.head_object_id != action.expected_head_object_id
                or f"refs/heads/{action.branch_name}" in observation.branch_refs
            ):
                raise RuntimeError("local Git feature branch state changed after intent")
            receipt = self._adapter.apply(action)
        if (
            receipt.before_object_id != action.expected_head_object_id
            or receipt.after_object_id != action.expected_head_object_id
        ):
            raise RuntimeError("local Git feature branch receipt changed the head")
        updated = replace(
            record, branch_receipt=receipt,
            authorization_decision_ids=(
                *record.authorization_decision_ids, decision.decision_id,
            ),
            revision=record.revision + 1, updated_at=self._clock(),
        )
        self._store.save(record.revision, updated)
        return updated

    def _begin_rollback(
        self, delivery_id, rollback_id, definition, changeset, original,
        session_id, principal_id, evidence, message,
    ):
        task = definition.task
        root = task.workspace_roots[0]
        observation = self._adapter.observe(task.task_id, Path(root))
        expected_head = original.commit_receipt.after_object_id
        if observation.head_object_id != expected_head:
            raise RuntimeError("local Git head changed before rollback delivery")
        if self._adapter.staged_paths(root):
            raise PermissionError("local Git rollback requires an empty staging area")
        paths = _git_stage_paths(changeset)
        now = self._clock()
        stage = GitLocalAction(
            f"stage-{delivery_id}", task.task_id, root,
            GitLocalActionKind.STAGE_PATHS, None, paths, None,
            rollback_id, evidence, expected_head, now,
        )
        commit = GitLocalAction(
            f"commit-{delivery_id}", task.task_id, root,
            GitLocalActionKind.COMMIT, None, (), message,
            rollback_id, evidence, expected_head, now,
        )
        decision = self._authorize(
            definition, None, session_id, principal_id, stage.action_id,
            changeset_id=rollback_id,
        )
        record = LocalGitDeliveryRecord(
            delivery_id, task.task_id, rollback_id, stage, commit,
            LocalGitDeliveryStatus.INTENT_RECORDED, (decision.decision_id,),
            0, now, now,
        )
        self._store.begin(record)
        return record

    def _stage(self, record, definition, session_id, principal_id):
        decision = self._authorize(
            definition, None, session_id, principal_id,
            record.stage_action.action_id, changeset_id=record.changeset_id,
        )
        current = self._adapter.staged_paths(record.stage_action.repository_root)
        if current and current != record.stage_action.paths:
            raise RuntimeError("local Git staging area changed after intent")
        receipt = self._adapter.apply(record.stage_action)
        if receipt.staged_paths != record.stage_action.paths:
            raise RuntimeError("local Git staged paths differ from approved changeset")
        updated = replace(
            record, status=LocalGitDeliveryStatus.STAGED,
            authorization_decision_ids=(*record.authorization_decision_ids, decision.decision_id),
            stage_receipt=receipt, revision=record.revision + 1,
            updated_at=self._clock(),
        )
        self._store.save(record.revision, updated)
        return updated

    def _commit(self, record, definition, session_id, principal_id):
        decision = self._authorize(
            definition, None, session_id, principal_id,
            record.commit_action.action_id, changeset_id=record.changeset_id,
        )
        observation = self._adapter.observe(
            record.task_id, Path(record.commit_action.repository_root),
        )
        if observation.head_object_id == record.commit_action.expected_head_object_id:
            receipt = self._adapter.apply(record.commit_action)
        else:
            receipt = self._adapter.reconcile_commit(
                record.commit_action, record.stage_action.paths,
            )
        updated = replace(
            record, status=LocalGitDeliveryStatus.COMMITTED,
            authorization_decision_ids=(*record.authorization_decision_ids, decision.decision_id),
            commit_receipt=receipt, revision=record.revision + 1,
            updated_at=self._clock(),
        )
        self._store.save(record.revision, updated)
        return updated

    def _authorize(
        self, definition, changeset, session_id, principal_id, action_id,
        *, changeset_id=None,
    ):
        task = definition.task
        request = EngineeringAuthorizationRequest(
            f"authorization-{uuid4().hex}", task.grant_id, principal_id,
            EngineeringAuthority.MODIFY, task.task_id, session_id, action_id,
            changeset_id or changeset.changeset_id, task.workspace_roots[0],
            None, None, None, None, None, None, None,
            EngineeringResourceImpact(30, 1, 1, 0, 0, 0),
        )
        decision = self._authorizer.authorize(request)
        if not decision.allowed or decision.request_id != request.request_id:
            raise PermissionError("local Git delivery lacks live modify authority")
        return decision

    @staticmethod
    def _validate(definition, changeset, evidence):
        task = definition.task
        if (
            len(task.workspace_roots) != 1
            or EngineeringAuthority.MODIFY not in task.authorities
            or EngineeringOperation.GIT_WRITE not in task.permitted_operations
            or changeset.task_id != task.task_id
            or changeset.status is not CandidateChangesetStatus.APPLIED
            or changeset.receipt is None
            or not changeset.receipt.applied_paths
            or not evidence
        ):
            raise PermissionError("local Git commit is outside the approved task envelope")

    @staticmethod
    def _same(record, definition, changeset, evidence, message):
        LocalGitDeliveryService._same_values(
            record, definition, changeset.changeset_id, evidence, message,
        )

    @staticmethod
    def _same_values(record, definition, changeset_id, evidence, message):
        if (
            record.task_id != definition.task.task_id
            or record.changeset_id != changeset_id
            or record.commit_action.verification_evidence_ids != evidence
            or record.commit_action.message != message
        ):
            raise RuntimeError("local Git delivery retry differs from recorded intent")

    def _require_original_delivery(self, definition, changeset):
        original = self._store.load(f"git-delivery-{changeset.changeset_id}")
        if (
            original is None
            or original.task_id != definition.task.task_id
            or original.changeset_id != changeset.changeset_id
            or original.status is not LocalGitDeliveryStatus.COMMITTED
            or original.commit_receipt is None
            or original.commit_receipt.after_object_id is None
        ):
            raise PermissionError("rollback requires the exact completed local delivery")
        return original

    @staticmethod
    def _validate_rollback(definition, changeset):
        task = definition.task
        if (
            len(task.workspace_roots) != 1
            or EngineeringAuthority.MODIFY not in task.authorities
            or EngineeringOperation.GIT_WRITE not in task.permitted_operations
            or changeset.task_id != task.task_id
            or changeset.status
            is not CandidateChangesetStatus.EXPLICITLY_ROLLED_BACK
            or changeset.receipt is None
            or changeset.rollback_receipt is None
            or not changeset.rollback_receipt.rollback_complete
            or not changeset.receipt.applied_paths
        ):
            raise PermissionError("local Git rollback is outside the approved task envelope")

    def _validate_precommit_rollback(self, definition, changeset):
        task = definition.task
        if (
            len(task.workspace_roots) != 1
            or EngineeringAuthority.MODIFY not in task.authorities
            or changeset.task_id != task.task_id
            or changeset.status not in {
                CandidateChangesetStatus.APPLIED,
                CandidateChangesetStatus.ROLLBACK_INTENT,
                CandidateChangesetStatus.EXPLICITLY_ROLLED_BACK,
                CandidateChangesetStatus.ROLLBACK_RECOVERY_REQUIRED,
            }
            or changeset.receipt is None
            or not changeset.receipt.applied_paths
            or self._store.load(
                f"git-delivery-{changeset.changeset_id}"
            ) is not None
        ):
            raise PermissionError(
                "pre-commit rollback is outside the approved task envelope"
            )


_BRANCH_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


def _feature_branch(task_id: str) -> str:
    slug = _BRANCH_COMPONENT.sub("-", task_id).strip(".-") or "task"
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:10]
    return f"fam/{slug[:120]}-{digest}"


def _protected_branch(branch: str) -> bool:
    return branch in {"main", "master", "trunk", "production", "prod"}


def _git_stage_paths(changeset: CandidateChangesetRecord) -> tuple[str, ...]:
    """Translate filesystem operations to exact Git-representable file paths."""
    paths = {
        item.path for item in changeset.preview.items
        if item.before_sha256 is not None or item.after_sha256 is not None
    }
    for operation in changeset.operations:
        if operation.kind is not CandidateOperationKind.MOVE:
            continue
        if operation.expected_before_sha256 is None:
            raise PermissionError(
                "directory move requires file-expanded Git delivery evidence"
            )
        paths.add(operation.source_path or "")
        paths.add(operation.path)
    paths.discard("")
    if not paths:
        raise PermissionError("approved changeset has no Git-representable file effect")
    return tuple(sorted(paths))
