"""Explicit, bounded grants for persistent local document indexing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import PurePath

from fam_os.memory.manifest import MemoryScope


DOCUMENT_INDEX_GRANT_VERSION = "fam.memory.document-index-grant/v1alpha1"
MAX_GRANT_LIFETIME = timedelta(days=90)
MAX_GRANT_FILES = 4_096
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_GRANT_BYTES = 512 * 1024 * 1024


class DocumentIndexGrantKind(str, Enum):
    FILE = "file"
    FOLDER = "folder"


@dataclass(frozen=True, slots=True)
class DocumentIndexGrant:
    grant_id: str
    root_path: str
    kind: DocumentIndexGrantKind
    scope: MemoryScope
    recursive: bool
    allowed_extensions: tuple[str, ...]
    max_files: int
    max_file_bytes: int
    max_total_bytes: int
    approved_by: str
    approved_at: datetime
    expires_at: datetime
    embedding_model_ref: str
    embedding_artifact_sha256: str
    contract_version: str = DOCUMENT_INDEX_GRANT_VERSION

    def __post_init__(self) -> None:
        identifiers = (self.grant_id, self.root_path, self.approved_by,
                       self.embedding_model_ref)
        if any(not value.strip() or "\x00" in value for value in identifiers):
            raise ValueError("document index grant identifiers must be canonical")
        path = PurePath(self.root_path)
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("document index grant root must be an absolute bounded path")
        if self.kind is DocumentIndexGrantKind.FILE and self.recursive:
            raise ValueError("a file grant cannot be recursive")
        if not self.allowed_extensions:
            raise ValueError("document index grant requires allowed extensions")
        canonical = tuple(sorted(set(self.allowed_extensions)))
        if self.allowed_extensions != canonical or any(
            not value.startswith(".") or value != value.lower()
            or len(value) < 2 or not value[1:].replace("-", "").isalnum()
            for value in self.allowed_extensions
        ):
            raise ValueError("allowed extensions must be unique sorted lowercase suffixes")
        if not 1 <= self.max_files <= MAX_GRANT_FILES:
            raise ValueError("document index file bound is invalid")
        if not 1 <= self.max_file_bytes <= MAX_FILE_BYTES:
            raise ValueError("document index per-file byte bound is invalid")
        if not self.max_file_bytes <= self.max_total_bytes <= MAX_GRANT_BYTES:
            raise ValueError("document index total byte bound is invalid")
        _aware(self.approved_at, "approval")
        _aware(self.expires_at, "expiry")
        lifetime = self.expires_at - self.approved_at
        if lifetime <= timedelta(0) or lifetime > MAX_GRANT_LIFETIME:
            raise ValueError("document index grant expiry must be within 90 days")
        _digest(self.embedding_artifact_sha256)

    def active_at(self, now: datetime) -> bool:
        _aware(now, "evaluation")
        return self.approved_at <= now < self.expires_at


@dataclass(frozen=True, slots=True)
class DocumentIndexReceipt:
    receipt_id: str
    grant_id: str
    indexed_document_ids: tuple[str, ...]
    indexed_chunk_count: int
    indexed_byte_count: int
    skipped_paths: tuple[str, ...]
    completed_at: datetime
    expires_at: datetime
    passed: bool
    contract_version: str = DOCUMENT_INDEX_GRANT_VERSION

    def __post_init__(self) -> None:
        if not self.receipt_id.strip() or not self.grant_id.strip():
            raise ValueError("document index receipt identifiers must not be empty")
        _aware(self.completed_at, "completion")
        _aware(self.expires_at, "expiry")
        if self.expires_at <= self.completed_at:
            raise ValueError("document index receipt must describe an active grant")
        if self.indexed_chunk_count < 0 or self.indexed_byte_count < 0:
            raise ValueError("document index receipt counts cannot be negative")
        expected = bool(self.indexed_document_ids) and self.indexed_chunk_count > 0
        if self.passed != expected:
            raise ValueError("document index receipt pass must derive from indexed content")


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"document index {name} time must be timezone-aware")


def _digest(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("document index artifact digest must be lowercase SHA-256")
