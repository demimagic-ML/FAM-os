"""Typed candidate-workspace transaction contracts and protection policy."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, positive, relative_path, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class CandidateOperationKind(StrEnum):
    CREATE_DIRECTORY = "create_directory"
    CREATE_FILE = "create_file"
    PATCH_FILE = "patch_file"
    MOVE = "move"
    DELETE = "delete"
    SET_EXECUTABLE = "set_executable"
    RESTORE = "restore"


class CandidateContentKind(StrEnum):
    TEXT = "text"
    BINARY = "binary"


class CandidateEntryKind(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"


class CandidateApplyStatus(StrEnum):
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    CONFLICT = "conflict"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True, slots=True)
class CandidateArtifactMetadata:
    key: str
    value: str

    def __post_init__(self) -> None:
        text(self.key, "key")
        text(self.value, "value")
        if len(self.value.encode("utf-8")) > 4_096:
            raise ValueError("artifact metadata value exceeds its bound")


@dataclass(frozen=True, slots=True)
class CandidateArtifact:
    artifact_id: str
    content_kind: CandidateContentKind
    media_type: str
    content_sha256: str
    size_bytes: int
    provenance: str
    source_name: str | None = None
    metadata: tuple[CandidateArtifactMetadata, ...] = ()

    def __post_init__(self) -> None:
        for name in ("artifact_id", "media_type", "provenance"):
            text(getattr(self, name), name)
        digest(self.content_sha256, "content_sha256", required=True)
        positive(self.size_bytes, "size_bytes", allow_zero=True)
        if "/" not in self.media_type or any(character.isspace() for character in self.media_type):
            raise ValueError("media_type must be a MIME media type")
        if self.source_name is not None:
            text(self.source_name, "source_name")
        keys = tuple(item.key for item in self.metadata)
        texts(keys, "artifact metadata keys")


@dataclass(frozen=True, slots=True)
class CandidateBaselineEntry:
    path: str
    kind: CandidateEntryKind
    content_sha256: str | None
    size_bytes: int
    executable: bool

    def __post_init__(self) -> None:
        relative_path(self.path, "path")
        digest(self.content_sha256, "content_sha256")
        positive(self.size_bytes, "size_bytes", allow_zero=True)
        if self.kind is CandidateEntryKind.FILE and self.content_sha256 is None:
            raise ValueError("file baseline entries require a digest")
        if self.kind is CandidateEntryKind.DIRECTORY and self.content_sha256 is not None:
            raise ValueError("directory baseline entries cannot have a content digest")


@dataclass(frozen=True, slots=True)
class CandidateWorkspace:
    candidate_id: str
    task_id: str
    baseline_id: str
    owner_workspace: str
    candidate_workspace: str
    created_at: datetime
    clone_strategy: str
    baseline_tree_sha256: str
    entries: tuple[CandidateBaselineEntry, ...]
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("candidate_id", "task_id", "baseline_id", "owner_workspace", "candidate_workspace", "clone_strategy"):
            text(getattr(self, name), name)
        aware(self.created_at, "created_at")
        digest(self.baseline_tree_sha256, "baseline_tree_sha256", required=True)
        paths = tuple(item.path for item in self.entries)
        texts(paths, "baseline paths")
        if paths != tuple(sorted(paths)):
            raise ValueError("baseline entries must be sorted")
        if self.owner_workspace == self.candidate_workspace:
            raise ValueError("candidate workspace must be isolated from owner workspace")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("candidate workspace contract version is unsupported")


@dataclass(frozen=True, slots=True)
class CandidateOperation:
    operation_id: str
    kind: CandidateOperationKind
    path: str
    expected_before_sha256: str | None = None
    artifact_id: str | None = None
    source_path: str | None = None
    executable: bool | None = None

    def __post_init__(self) -> None:
        text(self.operation_id, "operation_id")
        relative_path(self.path, "path")
        digest(self.expected_before_sha256, "expected_before_sha256")
        if self.artifact_id is not None:
            text(self.artifact_id, "artifact_id")
        if self.source_path is not None:
            relative_path(self.source_path, "source_path")
        if self.kind in {CandidateOperationKind.CREATE_FILE, CandidateOperationKind.PATCH_FILE, CandidateOperationKind.RESTORE} and self.artifact_id is None:
            raise ValueError("content operation requires an artifact")
        if self.kind is CandidateOperationKind.MOVE and self.source_path is None:
            raise ValueError("move requires source_path")
        if self.kind is CandidateOperationKind.SET_EXECUTABLE and self.executable is None:
            raise ValueError("executable operation requires the desired bit")
        if self.kind not in {CandidateOperationKind.CREATE_FILE, CandidateOperationKind.PATCH_FILE, CandidateOperationKind.RESTORE} and self.artifact_id is not None:
            raise ValueError("artifact is not valid for this operation")
        if self.kind is not CandidateOperationKind.MOVE and self.source_path is not None:
            raise ValueError("source_path is valid only for move")
        if self.kind is not CandidateOperationKind.SET_EXECUTABLE and self.executable is not None:
            raise ValueError("executable is valid only for set_executable")


@dataclass(frozen=True, slots=True)
class CandidatePreviewItem:
    path: str
    operation_kind: CandidateOperationKind
    before_sha256: str | None
    after_sha256: str | None
    media_type: str | None
    size_delta_bytes: int
    preview: str
    risk_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        relative_path(self.path, "path")
        digest(self.before_sha256, "before_sha256")
        digest(self.after_sha256, "after_sha256")
        if len(self.preview.encode("utf-8")) > 65_536:
            raise ValueError("candidate preview exceeds its bound")
        texts(self.risk_codes, "risk_codes")


@dataclass(frozen=True, slots=True)
class CandidateTransactionPreview:
    transaction_id: str
    candidate_id: str
    baseline_tree_sha256: str
    generated_at: datetime
    items: tuple[CandidatePreviewItem, ...]
    verification_evidence_ids: tuple[str, ...]
    verification_summary: str
    rollback_summary: str
    required_confirmation: bool = True
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("transaction_id", "candidate_id", "verification_summary", "rollback_summary"):
            text(getattr(self, name), name)
        digest(self.baseline_tree_sha256, "baseline_tree_sha256", required=True)
        aware(self.generated_at, "generated_at")
        texts(self.verification_evidence_ids, "verification_evidence_ids")
        if not self.items or not self.required_confirmation:
            raise ValueError("transaction preview requires changes and confirmation")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("transaction preview contract version is unsupported")


@dataclass(frozen=True, slots=True)
class CandidateApplyReceipt:
    transaction_id: str
    candidate_id: str
    completed_at: datetime
    status: CandidateApplyStatus
    applied_paths: tuple[str, ...]
    preserved_owner_paths: tuple[str, ...]
    journal_sha256: str
    rollback_complete: bool
    message: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("transaction_id", "candidate_id", "message"):
            text(getattr(self, name), name)
        aware(self.completed_at, "completed_at")
        texts(self.applied_paths, "applied_paths")
        texts(self.preserved_owner_paths, "preserved_owner_paths")
        digest(self.journal_sha256, "journal_sha256", required=True)
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("candidate apply receipt contract version is unsupported")


@dataclass(frozen=True, slots=True)
class EngineeringSelfUpdatePolicy:
    source_checkout_roots: tuple[str, ...]
    running_install_roots: tuple[str, ...]
    trust_root_paths: tuple[str, ...]
    active_release_paths: tuple[str, ...]
    live_policy_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        texts(self.source_checkout_roots, "source_checkout_roots")
        protected = self.running_install_roots + self.trust_root_paths + self.active_release_paths + self.live_policy_paths
        texts(protected, "protected self-update paths")
        if set(self.source_checkout_roots) & set(protected):
            raise ValueError("source checkout and protected runtime paths must be separate")

    def authorize_source_path(self, path: str) -> None:
        relative_path(path, "path")
        protected = (
            self.running_install_roots + self.trust_root_paths
            + self.active_release_paths + self.live_policy_paths
        )
        if any(_within(path, item) for item in protected):
            raise PermissionError("self-update cannot modify running installation or trust state")
        if not any(_within(path, item) for item in self.source_checkout_roots):
            raise PermissionError("self-update path is outside an approved source checkout")


def _within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")
