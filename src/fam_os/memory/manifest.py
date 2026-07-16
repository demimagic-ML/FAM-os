"""Versioned permissioned memory-record metadata contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


MEMORY_RECORD_MANIFEST_CONTRACT_VERSION = "fam.memory.record/v1alpha1"


class MemoryRecordKind(StrEnum):
    SESSION = "session"
    WORKING = "working"
    DOCUMENT_CHUNK = "document_chunk"
    PREFERENCE = "preference"
    EVENT = "event"
    SUMMARY = "summary"


class MemorySensitivity(StrEnum):
    PRIVATE = "private"
    RESTRICTED = "restricted"


class MemorySourceKind(StrEnum):
    USER = "user"
    APPLICATION = "application"
    IMPORT = "import"
    DERIVED = "derived"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class MemoryContentDigest:
    algorithm: str
    value: str

    def __post_init__(self) -> None:
        algorithm = self.algorithm.strip().lower()
        value = self.value.strip().lower()
        if not algorithm or len(value) < 32:
            raise ValueError("memory content digest must name an algorithm and value")
        if any(character not in "0123456789abcdef" for character in value):
            raise ValueError("memory content digest must be hexadecimal")
        object.__setattr__(self, "algorithm", algorithm)
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class MemoryScope:
    owner_id: str
    purpose_ids: tuple[str, ...]
    application_ids: tuple[str, ...] = ()
    workspace_ids: tuple[str, ...] = ()
    session_id: str | None = None

    def __post_init__(self) -> None:
        if not self.owner_id.strip():
            raise ValueError("memory owner_id must not be empty")
        self._require_unique("purpose_ids", self.purpose_ids, required=True)
        self._require_unique("application_ids", self.application_ids)
        self._require_unique("workspace_ids", self.workspace_ids)
        if self.session_id is not None and not self.session_id.strip():
            raise ValueError("session_id must not be empty when provided")

    @staticmethod
    def _require_unique(name: str, values: tuple[str, ...], required: bool = False) -> None:
        if required and not values:
            raise ValueError(f"{name} must not be empty")
        if any(not value.strip() for value in values) or len(set(values)) != len(values):
            raise ValueError(f"{name} values must be non-empty and unique")


@dataclass(frozen=True, slots=True)
class MemoryProvenance:
    source_kind: MemorySourceKind
    source_id: str
    created_by: str
    captured_at: datetime
    parent_record_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.created_by.strip():
            raise ValueError("memory source_id and created_by must not be empty")
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        if any(not item.strip() for item in self.parent_record_ids):
            raise ValueError("parent memory record IDs must not be empty")
        if len(set(self.parent_record_ids)) != len(self.parent_record_ids):
            raise ValueError("parent memory record IDs must be unique")
        if self.source_kind is MemorySourceKind.DERIVED and not self.parent_record_ids:
            raise ValueError("derived memory requires parent record provenance")


@dataclass(frozen=True, slots=True)
class MemoryRecordManifest:
    record_id: str
    kind: MemoryRecordKind
    created_at: datetime
    content_schema_id: str
    content_media_type: str
    content_size_bytes: int
    content_digest: MemoryContentDigest
    scope: MemoryScope
    provenance: MemoryProvenance
    sensitivity: MemorySensitivity
    retention_policy_id: str
    expires_at: datetime | None = None
    contract_version: str = MEMORY_RECORD_MANIFEST_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "record_id",
            "content_schema_id",
            "content_media_type",
            "retention_policy_id",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.contract_version != MEMORY_RECORD_MANIFEST_CONTRACT_VERSION:
            raise ValueError("unsupported memory record contract_version")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.content_size_bytes < 0:
            raise ValueError("content_size_bytes cannot be negative")
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError("expires_at must be timezone-aware")
            if self.expires_at <= self.created_at:
                raise ValueError("expires_at must follow created_at")
        if self.record_id in self.provenance.parent_record_ids:
            raise ValueError("memory record cannot derive from itself")
        if self.kind in (MemoryRecordKind.SESSION, MemoryRecordKind.WORKING):
            if self.scope.session_id is None:
                raise ValueError("session and working memory require session scope")
