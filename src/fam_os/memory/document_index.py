"""Approval-only durable document indexing and scoped retrieval."""

import hashlib
import json
import math

from fam_os.core.ports.embedding import EmbeddingRequest, EmbeddingRuntime
from fam_os.memory.access import MemoryAccessContext, scope_allows
from fam_os.memory.document_contracts import (
    DocumentIndexApproval, DocumentRetrievalHit, IndexedDocumentChunk,
)
from fam_os.memory.document_repository import SqliteDocumentIndexRepository
from fam_os.memory.manifest import MemoryScope


class ApprovedDocumentIndex:
    def __init__(self, repository: SqliteDocumentIndexRepository, runtime: EmbeddingRuntime) -> None:
        self._repository = repository
        self._runtime = runtime

    def index(self, approval: DocumentIndexApproval, content: str, chunks: tuple[str, ...]) -> None:
        records = self._records(approval, content, chunks)
        self._repository.add(approval, records)

    def replace(self, approval: DocumentIndexApproval, content: str, chunks: tuple[str, ...]) -> None:
        self._repository.replace(approval, self._records(approval, content, chunks))

    def _records(self, approval, content, chunks):
        if hashlib.sha256(content.encode()).hexdigest() != approval.source_sha256:
            raise ValueError("approved source digest does not match content")
        if not chunks or "".join(chunks) != content:
            raise ValueError("document chunks must exactly reconstruct approved content")
        response = self._runtime.embed(EmbeddingRequest(approval.embedding_model_ref, chunks))
        if len(response.vectors) != len(chunks):
            raise ValueError("embedding count does not match document chunks")
        records = tuple(_chunk(approval.document_id, index, text, vector)
                        for index, (text, vector) in enumerate(zip(chunks, response.vectors, strict=True)))
        return records

    def retrieve(self, query: str, context: MemoryAccessContext, top_k: int = 5):
        if not query.strip() or top_k <= 0:
            raise ValueError("document retrieval requires query and positive top_k")
        rows = tuple(row for row in self._repository.rows() if _allowed(row, context))
        if not rows:
            return ()
        model_refs = {row[13] for row in rows}
        if len(model_refs) != 1:
            raise ValueError("one retrieval request cannot mix embedding models")
        query_vector = self._runtime.embed(EmbeddingRequest(
            next(iter(model_refs)), (query,),
        )).vectors[0]
        hits = tuple(_hit(row, query_vector) for row in rows)
        return tuple(sorted(hits, key=lambda item: (-item.score, item.chunk_id))[:top_k])


def _chunk(document_id, ordinal, content, embedding):
    chunk_id = f"{document_id}:chunk:{ordinal}"
    return IndexedDocumentChunk(
        chunk_id, document_id, ordinal, content,
        hashlib.sha256(content.encode()).hexdigest(), embedding,
    )


def _allowed(row, context):
    scope = MemoryScope(row[8], tuple(json.loads(row[9])), tuple(json.loads(row[10])),
                        tuple(json.loads(row[11])), row[12])
    return scope_allows(scope, context)


def _hit(row, query_vector):
    vector = tuple(json.loads(row[5]))
    score = _cosine(query_vector, vector)
    return DocumentRetrievalHit(row[0], row[1], row[3], score, row[6], row[7])


def _cosine(left, right):
    denominator = math.sqrt(sum(x*x for x in left)) * math.sqrt(sum(x*x for x in right))
    return sum(x*y for x, y in zip(left, right, strict=True)) / denominator if denominator else 0.0
