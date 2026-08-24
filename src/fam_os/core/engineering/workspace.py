"""Immutable workspace observations and proposed file mutations."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import (
    aware,
    digest,
    positive,
    relative_path,
    text,
    texts,
    unique_enum,
)
from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class FileOperationKind(StrEnum):
    CREATE = "create"
    REPLACE = "replace"
    DELETE = "delete"
    MOVE = "move"


@dataclass(frozen=True, slots=True)
class WorkspaceEntry:
    path: str
    content_sha256: str
    size_bytes: int
    executable: bool

    def __post_init__(self) -> None:
        relative_path(self.path, "path")
        digest(self.content_sha256, "content_sha256", required=True)
        positive(self.size_bytes, "size_bytes", allow_zero=True)


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    snapshot_id: str
    task_id: str
    captured_at: datetime
    workspace_root: str
    revision: str | None
    entries: tuple[WorkspaceEntry, ...]
    tree_sha256: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.snapshot_id, "snapshot_id")
        text(self.task_id, "task_id")
        text(self.workspace_root, "workspace_root")
        aware(self.captured_at, "captured_at")
        if self.revision is not None:
            text(self.revision, "revision")
        paths = tuple(entry.path for entry in self.entries)
        texts(paths, "entry paths")
        if paths != tuple(sorted(paths)):
            raise ValueError("workspace entries must be sorted by path")
        digest(self.tree_sha256, "tree_sha256", required=True)
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("workspace snapshot contract version is unsupported")


@dataclass(frozen=True, slots=True)
class FileOperation:
    operation_id: str
    kind: FileOperationKind
    path: str
    expected_before_sha256: str | None
    content_sha256: str | None
    source_path: str | None
    reversible: bool
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.operation_id, "operation_id")
        relative_path(self.path, "path")
        digest(self.expected_before_sha256, "expected_before_sha256")
        digest(self.content_sha256, "content_sha256")
        if self.source_path is not None:
            relative_path(self.source_path, "source_path")
        if self.kind is FileOperationKind.CREATE:
            if self.content_sha256 is None or self.expected_before_sha256 is not None:
                raise ValueError("create requires content and no prior digest")
        elif self.kind is FileOperationKind.REPLACE:
            if self.content_sha256 is None or self.expected_before_sha256 is None:
                raise ValueError("replace requires prior and proposed digests")
        elif self.kind is FileOperationKind.DELETE:
            if self.expected_before_sha256 is None or self.content_sha256 is not None:
                raise ValueError("delete requires only a prior digest")
        elif self.kind is FileOperationKind.MOVE:
            if self.source_path is None or self.expected_before_sha256 is None:
                raise ValueError("move requires a source path and prior digest")
            if self.source_path == self.path:
                raise ValueError("move source and destination must differ")
        if self.kind is not FileOperationKind.MOVE and self.source_path is not None:
            raise ValueError("source_path is valid only for move")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("file operation contract version is unsupported")


@dataclass(frozen=True, slots=True)
class ChangeSetProposal:
    proposal_id: str
    task_id: str
    snapshot_id: str
    created_at: datetime
    rationale: str
    operations: tuple[FileOperation, ...]
    required_authorities: tuple[EngineeringAuthority, ...]
    estimated_changed_bytes: int
    reversible: bool
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("proposal_id", "task_id", "snapshot_id", "rationale"):
            text(getattr(self, name), name)
        aware(self.created_at, "created_at")
        if not self.operations:
            raise ValueError("change-set proposal must contain operations")
        operation_ids = tuple(operation.operation_id for operation in self.operations)
        texts(operation_ids, "operation ids")
        unique_enum(self.required_authorities, "required_authorities")
        if EngineeringAuthority.MODIFY not in self.required_authorities:
            raise ValueError("change-set proposal requires modify authority")
        positive(self.estimated_changed_bytes, "estimated_changed_bytes", allow_zero=True)
        if self.reversible and any(not operation.reversible for operation in self.operations):
            raise ValueError("reversible proposal cannot contain irreversible operations")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("change-set proposal contract version is unsupported")
