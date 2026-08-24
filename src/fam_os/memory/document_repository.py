"""Typed persistence boundary for approved local document indexes."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from fam_os.memory.document_contracts import DocumentIndexApproval, IndexedDocumentChunk
from fam_os.memory.manifest import MemoryScope


@dataclass(frozen=True, slots=True)
class DocumentIndexRecord:
    approval: DocumentIndexApproval
    chunk: IndexedDocumentChunk


class DocumentIndexRepository(Protocol):
    def add(
        self, approval: DocumentIndexApproval, chunks: tuple[IndexedDocumentChunk, ...],
    ) -> None: ...

    def replace(
        self, approval: DocumentIndexApproval, chunks: tuple[IndexedDocumentChunk, ...],
    ) -> None: ...

    def approval(self, document_id: str) -> DocumentIndexApproval | None: ...

    def chunks(self, document_id: str) -> tuple[IndexedDocumentChunk, ...]: ...

    def records(self) -> tuple[DocumentIndexRecord, ...]: ...

    def delete(self, document_id: str) -> bool: ...


class SqliteDocumentIndexRepository:
    """Standalone Phase 10 repository retained for component-level evidence."""

    def __init__(self, path: Path, cipher=None) -> None:
        self._connection = sqlite3.connect(path)
        self._cipher = cipher
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript(_SCHEMA)

    def add(
        self, approval: DocumentIndexApproval, chunks: tuple[IndexedDocumentChunk, ...],
    ) -> None:
        with self._connection:
            self._insert(approval, chunks)

    def replace(
        self, approval: DocumentIndexApproval, chunks: tuple[IndexedDocumentChunk, ...],
    ) -> None:
        with self._connection:
            self._connection.execute(
                "DELETE FROM documents WHERE document_id=?", (approval.document_id,),
            )
            self._insert(approval, chunks)

    def approval(self, document_id: str) -> DocumentIndexApproval | None:
        row = self._connection.execute(
            "SELECT * FROM documents WHERE document_id=?", (document_id,),
        ).fetchone()
        return None if row is None else _approval(row)

    def document(self, document_id: str) -> DocumentIndexApproval | None:
        """Compatibility alias for the typed approval lookup."""
        return self.approval(document_id)

    def chunks(self, document_id: str) -> tuple[IndexedDocumentChunk, ...]:
        rows = self._connection.execute(
            "SELECT c.*,d.owner_id FROM chunks c JOIN documents d USING(document_id) "
            "WHERE c.document_id=? ORDER BY c.ordinal", (document_id,),
        ).fetchall()
        return tuple(self._decoded_chunk(row[:6], str(row[6])) for row in rows)

    def records(self) -> tuple[DocumentIndexRecord, ...]:
        values: list[DocumentIndexRecord] = []
        identifiers = self._connection.execute(
            "SELECT document_id FROM documents ORDER BY document_id",
        ).fetchall()
        for row in identifiers:
            approval = self.approval(str(row[0]))
            if approval is None:
                raise RuntimeError("document disappeared during index enumeration")
            values.extend(DocumentIndexRecord(approval, chunk) for chunk in self.chunks(approval.document_id))
        return tuple(values)

    def rows(self) -> tuple[DocumentIndexRecord, ...]:
        """Compatibility alias returning typed records rather than positional tuples."""
        return self.records()

    def delete(self, document_id: str) -> bool:
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM documents WHERE document_id=?", (document_id,),
            )
        return cursor.rowcount == 1

    def _insert(
        self, approval: DocumentIndexApproval, chunks: tuple[IndexedDocumentChunk, ...],
    ) -> None:
        scope = approval.scope
        self._connection.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                approval.document_id, approval.source_locator, approval.source_sha256,
                scope.owner_id, json.dumps(scope.purpose_ids),
                json.dumps(scope.application_ids), json.dumps(scope.workspace_ids),
                scope.session_id, approval.approved_by, approval.approved_at.isoformat(),
                approval.embedding_model_ref, approval.embedding_artifact_sha256,
                approval.contract_version, approval.grant_id,
                None if approval.expires_at is None else approval.expires_at.isoformat(),
            ),
        )
        self._connection.executemany(
            "INSERT INTO chunks VALUES (?,?,?,?,?,?)",
            (self._encoded_chunk(scope.owner_id, item) for item in chunks),
        )

    def _encoded_chunk(self, owner_id: str, item: IndexedDocumentChunk) -> tuple[object, ...]:
        content, embedding = item.content, json.dumps(item.embedding)
        if self._cipher is not None:
            content = self._cipher.encrypt(owner_id, content.encode())
            embedding = self._cipher.encrypt(owner_id, embedding.encode())
        return (
            item.chunk_id, item.document_id, item.ordinal, content,
            item.content_sha256, embedding,
        )

    def _decoded_chunk(self, row: tuple[object, ...], owner_id: str) -> IndexedDocumentChunk:
        values = list(row)
        if self._cipher is not None:
            values[3] = self._cipher.decrypt(owner_id, values[3]).decode()
            values[5] = self._cipher.decrypt(owner_id, values[5]).decode()
        return IndexedDocumentChunk(
            str(values[0]), str(values[1]), int(str(values[2])), str(values[3]),
            str(values[4]), tuple(float(value) for value in json.loads(str(values[5]))),
        )

    def close(self) -> None:
        self._connection.close()


def _approval(row: tuple[object, ...]) -> DocumentIndexApproval:
    scope = MemoryScope(
        str(row[3]), tuple(json.loads(str(row[4]))),
        tuple(json.loads(str(row[5]))), tuple(json.loads(str(row[6]))),
        None if row[7] is None else str(row[7]),
    )
    return DocumentIndexApproval(
        document_id=str(row[0]), source_locator=str(row[1]), source_sha256=str(row[2]),
        scope=scope, approved_by=str(row[8]), approved_at=datetime.fromisoformat(str(row[9])),
        embedding_model_ref=str(row[10]), embedding_artifact_sha256=str(row[11]),
        contract_version=str(row[12]), grant_id=None if row[13] is None else str(row[13]),
        expires_at=None if row[14] is None else datetime.fromisoformat(str(row[14])),
    )


_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents(
 document_id TEXT PRIMARY KEY,source_locator TEXT,source_sha256 TEXT,owner_id TEXT,
 purpose_ids TEXT,application_ids TEXT,workspace_ids TEXT,session_id TEXT,
 approved_by TEXT,approved_at TEXT,embedding_model_ref TEXT,
 embedding_artifact_sha256 TEXT,contract_version TEXT,grant_id TEXT,expires_at TEXT);
CREATE TABLE IF NOT EXISTS chunks(
 chunk_id TEXT PRIMARY KEY,document_id TEXT REFERENCES documents(document_id) ON DELETE CASCADE,
 ordinal INTEGER,content TEXT,content_sha256 TEXT,embedding TEXT);
"""
