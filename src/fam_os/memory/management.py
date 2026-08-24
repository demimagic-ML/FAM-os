"""User inspection, correction, export, and deletion for document memory."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.memory.access import scope_allows
from fam_os.memory.document_contracts import DocumentIndexApproval
from fam_os.memory.document_index import ApprovedDocumentIndex
from fam_os.memory.document_repository import DocumentIndexRepository
from fam_os.memory.lifecycle_contracts import MemoryDeletionReceipt, MemoryDeletionRequest

MEMORY_MANAGEMENT_CONTRACT_VERSION = "fam.memory.management/v1alpha1"
MAX_MANAGED_DOCUMENT_BYTES = 1_048_576


class DocumentManagementOperation(StrEnum):
    CORRECT = "correct"
    EXPIRE = "expire"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class DocumentInspection:
    approval: DocumentIndexApproval
    chunk_count: int
    content_bytes: int
    content_sha256: str
    contract_version: str = MEMORY_MANAGEMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.chunk_count < 1 or self.content_bytes < 1:
            raise ValueError("document inspection requires indexed content")
        _digest(self.content_sha256)
        if self.content_sha256 != self.approval.source_sha256:
            raise ValueError("document inspection digest must match its approval")


@dataclass(frozen=True, slots=True)
class DocumentCorrectionRequest:
    request_id: str
    document_id: str
    expected_content_sha256: str
    replacement_content: str
    replacement_content_sha256: str
    confirmed: bool
    contract_version: str = MEMORY_MANAGEMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _texts(self.request_id, self.document_id)
        _digest(self.expected_content_sha256)
        _digest(self.replacement_content_sha256)
        encoded = self.replacement_content.encode("utf-8")
        if not self.replacement_content.strip() or len(encoded) > MAX_MANAGED_DOCUMENT_BYTES:
            raise ValueError("replacement content must be nonempty and bounded")
        if hashlib.sha256(encoded).hexdigest() != self.replacement_content_sha256:
            raise ValueError("replacement content digest does not match")
        if not self.confirmed:
            raise PermissionError("document correction requires explicit confirmation")


@dataclass(frozen=True, slots=True)
class DocumentExpirationRequest:
    request_id: str
    grant_id: str
    confirmed: bool
    contract_version: str = MEMORY_MANAGEMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _texts(self.request_id, self.grant_id)
        if not self.confirmed:
            raise PermissionError("document expiry requires explicit confirmation")


@dataclass(frozen=True, slots=True)
class DocumentDeletionRequest:
    request_id: str
    document_id: str
    expected_content_sha256: str
    confirmed: bool
    contract_version: str = MEMORY_MANAGEMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _texts(self.request_id, self.document_id)
        _digest(self.expected_content_sha256)
        if not self.confirmed:
            raise PermissionError("document deletion requires explicit confirmation")


@dataclass(frozen=True, slots=True)
class DocumentManagementReceipt:
    receipt_id: str
    request_id: str
    operation: DocumentManagementOperation
    target_id: str
    owner_id: str
    performed_by: str
    performed_at: datetime
    previous_content_sha256: str
    resulting_content_sha256: str | None
    affected_document_ids: tuple[str, ...]
    tombstone_sha256: str
    payload_removed: bool
    contract_version: str = MEMORY_MANAGEMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _texts(
            self.receipt_id, self.request_id, self.target_id,
            self.owner_id, self.performed_by,
        )
        if not isinstance(self.operation, DocumentManagementOperation):
            raise ValueError("document management operation is invalid")
        if self.performed_at.tzinfo is None or self.performed_at.utcoffset() is None:
            raise ValueError("document management receipt time must be timezone-aware")
        _digest(self.previous_content_sha256)
        _digest(self.tombstone_sha256)
        identifiers = tuple(value.strip() for value in self.affected_document_ids)
        if any(not value for value in identifiers):
            raise ValueError("affected document IDs must be nonempty")
        if not identifiers and self.operation is not DocumentManagementOperation.EXPIRE:
            raise ValueError("document management receipt requires affected documents")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("affected document IDs must be unique")
        object.__setattr__(self, "affected_document_ids", identifiers)
        if self.operation is DocumentManagementOperation.CORRECT:
            if self.resulting_content_sha256 is None or self.payload_removed:
                raise ValueError("correction receipt requires replacement content")
            _digest(self.resulting_content_sha256)
            if identifiers != (self.target_id,):
                raise ValueError("correction receipt target must be the affected document")
        else:
            if self.resulting_content_sha256 is not None or not self.payload_removed:
                raise ValueError("removal receipt cannot retain a resulting digest")
            if self.operation is DocumentManagementOperation.DELETE and identifiers != (
                self.target_id,
            ):
                raise ValueError("deletion receipt target must be the affected document")


@dataclass(frozen=True, slots=True)
class MemoryDocumentExport:
    approval: DocumentIndexApproval
    content: str
    content_sha256: str
    contract_version: str = MEMORY_MANAGEMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if hashlib.sha256(self.content.encode()).hexdigest() != self.content_sha256:
            raise ValueError("memory export content digest does not match")


@dataclass(frozen=True, slots=True)
class MemoryManagementEvidence:
    evidence_id: str
    inspected: bool
    correction_visible: bool
    export_digest_verified: bool
    deletion_payload_removed: bool
    remaining_chunk_count: int
    passed: bool
    contract_version: str = MEMORY_MANAGEMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        expected = all((self.inspected, self.correction_visible,
                        self.export_digest_verified, self.deletion_payload_removed))
        expected = expected and self.remaining_chunk_count == 0
        if self.passed != expected:
            raise ValueError("memory management evidence pass must derive from checks")


class DocumentMemoryManager:
    def __init__(self, repository: DocumentIndexRepository, index: ApprovedDocumentIndex) -> None:
        self._repository = repository
        self._index = index

    def inspect(self, document_id: str, context) -> DocumentIndexApproval | None:
        return self._authorized(document_id, context)

    def export(self, document_id: str, context) -> MemoryDocumentExport:
        approval = self._authorized(document_id, context)
        if approval is None:
            raise PermissionError("document memory scope denied")
        content = "".join(value.content for value in self._repository.chunks(document_id))
        digest = hashlib.sha256(content.encode()).hexdigest()
        if digest != approval.source_sha256:
            raise ValueError("exported document digest does not match approval")
        return MemoryDocumentExport(approval, content, digest)

    def correct(self, approval, content, chunks, context) -> None:
        if self._authorized(approval.document_id, context) is None:
            raise PermissionError("document correction scope denied")
        self._index.replace(approval, content, chunks)

    def delete(
        self, request: MemoryDeletionRequest, context, now: datetime,
    ) -> MemoryDeletionReceipt:
        approval = self._authorized(request.record_id, context)
        if approval is None or approval.scope.owner_id != request.owner_id:
            raise PermissionError("document deletion scope denied")
        content = "".join(value.content for value in self._repository.chunks(request.record_id))
        removed = self._repository.delete(request.record_id)
        tombstone = hashlib.sha256(
            f"{request.request_id}|{request.record_id}|{now.isoformat()}".encode(),
        ).hexdigest()
        return MemoryDeletionReceipt(
            request.request_id, request.record_id, now,
            hashlib.sha256(content.encode()).hexdigest(), tombstone, removed,
        )

    def _authorized(self, document_id: str, context) -> DocumentIndexApproval | None:
        approval = self._repository.approval(document_id)
        return approval if approval is not None and scope_allows(approval.scope, context) else None


def _texts(*values: str) -> None:
    if any(not isinstance(value, str) or not value.strip() or "\x00" in value for value in values):
        raise ValueError("document management identifiers must be strict nonempty text")


def _digest(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("document management digests must be lowercase SHA-256")
