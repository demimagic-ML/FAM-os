"""User inspection, correction, export, and deletion for document memory."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from fam_os.memory.access import scope_allows
from fam_os.memory.document_contracts import DocumentIndexApproval
from fam_os.memory.document_index import ApprovedDocumentIndex
from fam_os.memory.document_repository import SqliteDocumentIndexRepository
from fam_os.memory.lifecycle_contracts import MemoryDeletionReceipt, MemoryDeletionRequest
from fam_os.memory.manifest import MemoryScope

MEMORY_MANAGEMENT_CONTRACT_VERSION = "fam.memory.management/v1alpha1"


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
    def __init__(self, repository: SqliteDocumentIndexRepository, index: ApprovedDocumentIndex) -> None:
        self._repository = repository
        self._index = index

    def inspect(self, document_id, context):
        row = self._authorized(document_id, context)
        return _approval(row) if row is not None else None

    def export(self, document_id, context):
        row = self._authorized(document_id, context)
        if row is None:
            raise PermissionError("document memory scope denied")
        content = "".join(value[3] for value in self._repository.chunks(document_id))
        digest = hashlib.sha256(content.encode()).hexdigest()
        if digest != row[2]:
            raise ValueError("exported document digest does not match approval")
        return MemoryDocumentExport(_approval(row), content, digest)

    def correct(self, approval, content, chunks, context):
        if self._authorized(approval.document_id, context) is None:
            raise PermissionError("document correction scope denied")
        self._index.replace(approval, content, chunks)

    def delete(self, request: MemoryDeletionRequest, context, now: datetime):
        row = self._authorized(request.record_id, context)
        if row is None or row[3] != request.owner_id:
            raise PermissionError("document deletion scope denied")
        content = "".join(value[3] for value in self._repository.chunks(request.record_id))
        self._repository.delete(request.record_id)
        tombstone = hashlib.sha256(f"{request.request_id}|{request.record_id}|{now.isoformat()}".encode()).hexdigest()
        return MemoryDeletionReceipt(
            request.request_id, request.record_id, now,
            hashlib.sha256(content.encode()).hexdigest(), tombstone, True,
        )

    def _authorized(self, document_id, context):
        row = self._repository.document(document_id)
        return row if row is not None and scope_allows(_scope(row), context) else None


def _scope(row):
    return MemoryScope(row[3], tuple(json.loads(row[4])), tuple(json.loads(row[5])),
                       tuple(json.loads(row[6])), row[7])


def _approval(row):
    return DocumentIndexApproval(
        row[0], row[1], row[2], _scope(row), row[8], datetime.fromisoformat(row[9]),
        row[10], row[11], row[12],
    )
