"""Typed local Git and separately approved remote-publication contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, relative_path, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class GitLocalActionKind(StrEnum):
    CREATE_BRANCH = "create_branch"
    STAGE_PATHS = "stage_paths"
    COMMIT = "commit"
    RESTORE_PATHS = "restore_paths"


class GitPublicationKind(StrEnum):
    PUSH = "push"
    DRAFT_CHANGE_REQUEST = "draft_change_request"
    FORCE_PUSH = "force_push"
    PROTECTED_REF_WRITE = "protected_ref_write"
    TAG_REF_CHANGE = "tag_ref_change"
    REMOTE_CHANGE = "remote_change"


@dataclass(frozen=True, slots=True)
class GitRepositoryObservation:
    observation_id: str
    task_id: str
    repository_root: str
    head_ref: str
    head_object_id: str | None
    status_porcelain: tuple[str, ...]
    branch_refs: tuple[str, ...]
    remote_names: tuple[str, ...]
    history_object_ids: tuple[str, ...]
    diff_sha256: str
    observed_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("observation_id", "task_id", "repository_root", "head_ref"):
            text(getattr(self, name), name)
        _object_id(self.head_object_id, "head_object_id")
        texts(self.status_porcelain, "Git status rows", unique=False)
        texts(self.branch_refs, "Git branch refs")
        texts(self.remote_names, "Git remote names")
        for value in self.history_object_ids:
            _object_id(value, "history object ID", required=True)
        digest(self.diff_sha256, "diff_sha256", required=True)
        aware(self.observed_at, "observed_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("Git observation contract version is unsupported")


@dataclass(frozen=True, slots=True)
class GitLocalAction:
    action_id: str
    task_id: str
    repository_root: str
    kind: GitLocalActionKind
    branch_name: str | None
    paths: tuple[str, ...]
    message: str | None
    approved_change_set_id: str
    verification_evidence_ids: tuple[str, ...]
    expected_head_object_id: str | None
    requested_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("action_id", "task_id", "repository_root", "approved_change_set_id"):
            text(getattr(self, name), name)
        for path in self.paths:
            relative_path(path, "Git action path")
        texts(self.verification_evidence_ids, "verification evidence IDs")
        _object_id(self.expected_head_object_id, "expected_head_object_id")
        if self.branch_name is not None:
            text(self.branch_name, "branch_name")
        if self.message is not None:
            text(self.message, "message")
        if self.kind is GitLocalActionKind.CREATE_BRANCH and self.branch_name is None:
            raise ValueError("branch creation requires an exact branch name")
        if self.kind in {GitLocalActionKind.STAGE_PATHS, GitLocalActionKind.RESTORE_PATHS} and not self.paths:
            raise ValueError("path-scoped Git action requires exact paths")
        if self.kind is GitLocalActionKind.COMMIT and (self.message is None or not self.verification_evidence_ids):
            raise ValueError("commit requires a message and verification evidence")
        aware(self.requested_at, "requested_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("Git local action contract version is unsupported")


@dataclass(frozen=True, slots=True)
class GitLocalActionReceipt:
    receipt_id: str
    action_id: str
    before_object_id: str | None
    after_object_id: str | None
    staged_paths: tuple[str, ...]
    status_sha256: str
    completed_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.receipt_id, "receipt_id")
        text(self.action_id, "action_id")
        _object_id(self.before_object_id, "before_object_id")
        _object_id(self.after_object_id, "after_object_id")
        texts(self.staged_paths, "staged paths")
        digest(self.status_sha256, "status_sha256", required=True)
        aware(self.completed_at, "completed_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("Git local receipt contract version is unsupported")


@dataclass(frozen=True, slots=True)
class GitPublicationApproval:
    approval_id: str
    task_id: str
    grant_id: str
    kind: GitPublicationKind
    repository_root: str
    remote_name: str
    remote_url_sha256: str
    source_ref: str
    target_ref: str
    expected_old_object_id: str | None
    proposed_new_object_id: str
    commit_object_ids: tuple[str, ...]
    complete_diff_sha256: str
    verification_evidence_ids: tuple[str, ...]
    title: str
    body: str
    credential_ref: str
    consequence_preview: tuple[str, ...]
    approved_at: datetime
    expires_at: datetime
    single_use: bool = True
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "approval_id", "task_id", "grant_id", "repository_root",
            "remote_name", "source_ref", "target_ref", "title", "body",
            "credential_ref",
        ):
            text(getattr(self, name), name)
        for name in ("remote_url_sha256", "proposed_new_object_id", "complete_diff_sha256"):
            if name == "proposed_new_object_id":
                _object_id(getattr(self, name), name, required=True)
            else:
                digest(getattr(self, name), name, required=True)
        _object_id(self.expected_old_object_id, "expected_old_object_id")
        for value in self.commit_object_ids:
            _object_id(value, "commit object ID", required=True)
        texts(self.verification_evidence_ids, "verification evidence IDs")
        texts(self.consequence_preview, "consequence preview")
        aware(self.approved_at, "approved_at")
        aware(self.expires_at, "expires_at")
        if self.expires_at <= self.approved_at or not self.single_use:
            raise ValueError("Git publication approval must expire and be single-use")
        if not self.verification_evidence_ids or not self.commit_object_ids:
            raise ValueError("Git publication requires commits and verification evidence")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("Git publication approval contract version is unsupported")


@dataclass(frozen=True, slots=True)
class GitPublicationReceipt:
    receipt_id: str
    approval_id: str
    provider_id: str
    remote_name: str
    target_ref: str
    observed_old_object_id: str | None
    published_new_object_id: str
    change_request_url: str | None
    draft: bool
    completed_at: datetime
    provider_evidence_sha256: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "approval_id", "provider_id", "remote_name", "target_ref"):
            text(getattr(self, name), name)
        _object_id(self.observed_old_object_id, "observed_old_object_id")
        _object_id(self.published_new_object_id, "published_new_object_id", required=True)
        digest(self.provider_evidence_sha256, "provider_evidence_sha256", required=True)
        if self.change_request_url is not None:
            text(self.change_request_url, "change_request_url")
        aware(self.completed_at, "completed_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("Git publication receipt contract version is unsupported")


def _object_id(value: str | None, name: str, *, required: bool = False) -> None:
    if value is None and not required:
        return
    if value is None or len(value) not in {40, 64}:
        raise ValueError(f"{name} must be a Git SHA-1 or SHA-256 object ID")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"{name} must be hexadecimal") from error
