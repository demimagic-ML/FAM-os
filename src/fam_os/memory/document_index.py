"""Approval-only durable document indexing and scoped retrieval."""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime

from fam_os.core.ports.embedding import EmbeddingRequest, EmbeddingRuntime
from fam_os.memory.access import MemoryAccessContext, scope_allows
from fam_os.memory.document_contracts import (
    DocumentIndexApproval,
    DocumentRetrievalHit,
    IndexedDocumentChunk,
)
from fam_os.memory.document_repository import DocumentIndexRecord, DocumentIndexRepository


class ApprovedDocumentIndex:
    def __init__(self, repository: DocumentIndexRepository, runtime: EmbeddingRuntime) -> None:
        self._repository = repository
        self._runtime = runtime

    def index(
        self, approval: DocumentIndexApproval, content: str, chunks: tuple[str, ...],
    ) -> None:
        self._repository.add(approval, self.prepare(approval, content, chunks))

    def replace(
        self, approval: DocumentIndexApproval, content: str, chunks: tuple[str, ...],
    ) -> None:
        self._repository.replace(approval, self.prepare(approval, content, chunks))

    def prepare(
        self, approval: DocumentIndexApproval, content: str, chunks: tuple[str, ...],
    ) -> tuple[IndexedDocumentChunk, ...]:
        """Validate and embed exact chunks without mutating persistence."""
        if hashlib.sha256(content.encode()).hexdigest() != approval.source_sha256:
            raise ValueError("approved source digest does not match content")
        if not chunks or "".join(chunks) != content:
            raise ValueError("document chunks must exactly reconstruct approved content")
        response = self._runtime.embed(EmbeddingRequest(approval.embedding_model_ref, chunks))
        if len(response.vectors) != len(chunks):
            raise ValueError("embedding count does not match document chunks")
        return tuple(
            _chunk(approval.document_id, index, text, vector)
            for index, (text, vector) in enumerate(zip(chunks, response.vectors, strict=True))
        )

    def retrieve(
        self, query: str, context: MemoryAccessContext, top_k: int = 5,
        *, now: datetime | None = None,
    ) -> tuple[DocumentRetrievalHit, ...]:
        if not query.strip() or top_k <= 0:
            raise ValueError("document retrieval requires query and positive top_k")
        evaluated_at = now or datetime.now(UTC)
        rows = tuple(
            row for row in self._repository.records()
            if _allowed(row, context, evaluated_at)
        )
        if not rows:
            return ()
        model_refs = {row.approval.embedding_model_ref for row in rows}
        if len(model_refs) != 1:
            raise ValueError("one retrieval request cannot mix embedding models")
        response = self._runtime.embed(EmbeddingRequest(next(iter(model_refs)), (query,)))
        if len(response.vectors) != 1:
            raise ValueError("embedding runtime returned an invalid query vector count")
        hits = tuple(_hit(row, response.vectors[0]) for row in rows)
        return tuple(sorted(hits, key=lambda item: (-item.score, item.chunk_id))[:top_k])


def _chunk(
    document_id: str, ordinal: int, content: str, embedding: tuple[float, ...],
) -> IndexedDocumentChunk:
    return IndexedDocumentChunk(
        f"{document_id}:chunk:{ordinal}", document_id, ordinal, content,
        hashlib.sha256(content.encode()).hexdigest(), embedding,
    )


def _allowed(
    record: DocumentIndexRecord, context: MemoryAccessContext, now: datetime,
) -> bool:
    approval = record.approval
    return (
        (approval.expires_at is None or now < approval.expires_at)
        and scope_allows(approval.scope, context)
    )


def _hit(record: DocumentIndexRecord, query_vector: tuple[float, ...]) -> DocumentRetrievalHit:
    chunk, approval = record.chunk, record.approval
    return DocumentRetrievalHit(
        chunk.chunk_id, chunk.document_id, chunk.content,
        _cosine(query_vector, chunk.embedding),
        approval.source_locator, approval.source_sha256,
    )


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding vectors must have equal dimensions")
    denominator = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(x * x for x in right))
    return sum(x * y for x, y in zip(left, right, strict=True)) / denominator if denominator else 0.0
