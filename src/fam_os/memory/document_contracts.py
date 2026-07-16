"""Approved document indexing and retrieval contracts."""

from dataclasses import dataclass
from datetime import datetime

from fam_os.memory.manifest import MemoryScope

DOCUMENT_INDEX_CONTRACT_VERSION = "fam.memory.document-index/v1alpha1"


@dataclass(frozen=True, slots=True)
class DocumentIndexApproval:
    document_id: str
    source_locator: str
    source_sha256: str
    scope: MemoryScope
    approved_by: str
    approved_at: datetime
    embedding_model_ref: str
    embedding_artifact_sha256: str
    contract_version: str = DOCUMENT_INDEX_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (
            self.document_id, self.source_locator, self.approved_by,
            self.embedding_model_ref,
        )):
            raise ValueError("document approval identifiers must not be empty")
        _digest(self.source_sha256)
        _digest(self.embedding_artifact_sha256)
        if self.approved_at.tzinfo is None:
            raise ValueError("document approval time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class IndexedDocumentChunk:
    chunk_id: str
    document_id: str
    ordinal: int
    content: str
    content_sha256: str
    embedding: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.chunk_id.strip() or not self.document_id.strip() or not self.content:
            raise ValueError("indexed document chunk fields must not be empty")
        if self.ordinal < 0 or not self.embedding:
            raise ValueError("document chunk ordinal and embedding are required")
        _digest(self.content_sha256)


@dataclass(frozen=True, slots=True)
class DocumentRetrievalHit:
    chunk_id: str
    document_id: str
    content: str
    score: float
    source_locator: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class DocumentIndexEvidence:
    evidence_id: str
    document_id: str
    source_sha256: str
    embedding_model_ref: str
    embedding_artifact_sha256: str
    indexed_chunk_count: int
    top_chunk_id: str
    denied_scope_hit_count: int
    database_sha256: str
    passed: bool
    contract_version: str = DOCUMENT_INDEX_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value in (self.source_sha256, self.embedding_artifact_sha256, self.database_sha256):
            _digest(value)
        expected = self.indexed_chunk_count > 0 and self.denied_scope_hit_count == 0
        if self.passed != expected:
            raise ValueError("document index evidence pass must derive from checks")


def _digest(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("document index digests must be lowercase SHA-256")
