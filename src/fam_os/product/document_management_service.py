"""Owner-authorized document inspection and receipt-bound management."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from fam_os.memory import (
    DocumentCorrectionRequest,
    DocumentDeletionRequest,
    DocumentExpirationRequest,
    DocumentInspection,
    DocumentManagementOperation,
    DocumentManagementReceipt,
    MemoryDocumentExport,
    document_chunks,
)
from fam_os.product.storage.document_management_repository import aggregate_document_state


class ProductDocumentManagementService:
    def __init__(
        self, repository, index, owner_id: str, model_loader=None, clock=None,
    ) -> None:
        if not owner_id.strip():
            raise ValueError("document management owner must not be empty")
        self._repository = repository
        self._index = index
        self._owner_id = owner_id
        self._loader = model_loader
        self._clock = clock or (lambda: datetime.now(UTC))

    def inspections(self) -> tuple[DocumentInspection, ...]:
        self._repository.purge_expired(self._clock())
        return tuple(self.inspect(value) for value in self._repository.document_ids())

    def inspect(self, document_id: str) -> DocumentInspection:
        approval, content, chunks = self._document(document_id)
        return DocumentInspection(
            approval, len(chunks), len(content.encode("utf-8")), approval.source_sha256,
        )

    def export(self, document_id: str) -> MemoryDocumentExport:
        approval, content, _chunks = self._document(document_id)
        return MemoryDocumentExport(approval, content, approval.source_sha256)

    def correct(self, request: DocumentCorrectionRequest) -> DocumentManagementReceipt:
        replay = self._replay(
            request.request_id, DocumentManagementOperation.CORRECT, request.document_id,
        )
        if replay is not None:
            return replay
        approval, _content, _chunks = self._document(request.document_id)
        if approval.source_sha256 != request.expected_content_sha256:
            raise ValueError("document changed before correction")
        grant = self._require_grant(approval.grant_id)
        replacement_bytes = len(request.replacement_content.encode("utf-8"))
        if replacement_bytes > grant.max_file_bytes:
            raise ValueError("replacement exceeds the approved per-file byte bound")
        if self._other_document_bytes(grant.grant_id, request.document_id) + replacement_bytes > grant.max_total_bytes:
            raise ValueError("replacement exceeds the approved total byte bound")
        if self._loader is not None:
            self._loader.ensure_model(approval.embedding_model_ref)
        updated = replace(approval, source_sha256=request.replacement_content_sha256)
        chunks = self._index.prepare(
            updated, request.replacement_content, document_chunks(request.replacement_content),
        )
        receipt = self._receipt(
            request.request_id, DocumentManagementOperation.CORRECT,
            request.document_id, request.expected_content_sha256,
            request.replacement_content_sha256, (request.document_id,), False,
        )
        replay = self._persist(
            request.request_id, DocumentManagementOperation.CORRECT,
            request.document_id, lambda: self._repository.replace_with_receipt(
                updated, chunks, request.expected_content_sha256, receipt,
            ),
        )
        return replay or receipt

    def expire(self, request: DocumentExpirationRequest) -> DocumentManagementReceipt:
        replay = self._replay(
            request.request_id, DocumentManagementOperation.EXPIRE, request.grant_id,
        )
        if replay is not None:
            return replay
        grant = self._require_grant(request.grant_id)
        identifiers = self._repository.document_ids(grant.grant_id)
        rows = tuple(
            (identifier, self._require_approval(identifier).source_sha256)
            for identifier in identifiers
        )
        previous = aggregate_document_state(rows)
        receipt = self._receipt(
            request.request_id, DocumentManagementOperation.EXPIRE,
            request.grant_id, previous, None, identifiers, True,
        )
        replay = self._persist(
            request.request_id, DocumentManagementOperation.EXPIRE,
            request.grant_id,
            lambda: self._repository.expire_with_receipt(request.grant_id, receipt),
        )
        return replay or receipt

    def delete(self, request: DocumentDeletionRequest) -> DocumentManagementReceipt:
        replay = self._replay(
            request.request_id, DocumentManagementOperation.DELETE, request.document_id,
        )
        if replay is not None:
            return replay
        approval, _content, _chunks = self._document(request.document_id)
        if approval.source_sha256 != request.expected_content_sha256:
            raise ValueError("document changed before deletion")
        receipt = self._receipt(
            request.request_id, DocumentManagementOperation.DELETE,
            request.document_id, approval.source_sha256, None,
            (request.document_id,), True,
        )
        replay = self._persist(
            request.request_id, DocumentManagementOperation.DELETE,
            request.document_id, lambda: self._repository.delete_with_receipt(
                request.document_id, request.expected_content_sha256, receipt,
            ),
        )
        return replay or receipt

    def receipts(self) -> tuple[DocumentManagementReceipt, ...]:
        return self._repository.receipts()

    def _document(self, document_id: str):
        self._repository.purge_expired(self._clock())
        approval = self._require_approval(document_id)
        chunks = self._repository.chunks(document_id)
        content = "".join(item.content for item in chunks)
        if hashlib.sha256(content.encode("utf-8")).hexdigest() != approval.source_sha256:
            raise ValueError("managed document digest does not match its approval")
        return approval, content, chunks

    def _require_approval(self, document_id: str):
        approval = self._repository.approval(document_id)
        if approval is None or approval.scope.owner_id != self._owner_id:
            raise KeyError("managed document does not exist")
        return approval

    def _require_grant(self, grant_id: str | None):
        if grant_id is None:
            raise KeyError("managed document grant does not exist")
        grant = self._repository.grant(grant_id)
        if grant is None or grant.scope.owner_id != self._owner_id:
            raise KeyError("managed document grant does not exist")
        if not grant.active_at(self._clock()):
            raise ValueError("managed document grant is expired")
        return grant

    def _other_document_bytes(self, grant_id: str, excluded: str) -> int:
        return sum(
            self.inspect(identifier).content_bytes
            for identifier in self._repository.document_ids(grant_id)
            if identifier != excluded
        )

    def _replay(self, request_id, operation, target_id):
        receipt = self._repository.receipt_for_request(request_id)
        if receipt is None:
            return None
        if receipt.operation is not operation or receipt.target_id != target_id:
            raise ValueError("document management request identity was reused")
        return receipt

    def _persist(self, request_id, operation, target_id, transition):
        try:
            transition()
        except Exception:
            replay = self._replay(request_id, operation, target_id)
            if replay is not None:
                return replay
            raise
        return None

    def _receipt(
        self, request_id, operation, target_id, previous, resulting,
        affected, payload_removed,
    ) -> DocumentManagementReceipt:
        now = self._clock()
        tombstone = hashlib.sha256(
            "\x00".join((
                request_id, operation.value, target_id, previous,
                resulting or "removed", now.isoformat(), *affected,
            )).encode("utf-8")
        ).hexdigest()
        return DocumentManagementReceipt(
            f"management-{uuid4()}", request_id, operation, target_id,
            self._owner_id, self._owner_id, now, previous, resulting,
            affected, tombstone, payload_removed,
        )
