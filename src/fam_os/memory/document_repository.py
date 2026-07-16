"""SQLite persistence for approved local document indexes."""

import json
import sqlite3
from pathlib import Path

from fam_os.memory.document_contracts import DocumentIndexApproval, IndexedDocumentChunk


class SqliteDocumentIndexRepository:
    def __init__(self, path: Path, cipher=None) -> None:
        self._connection = sqlite3.connect(path)
        self._cipher = cipher
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript(_SCHEMA)

    def add(self, approval: DocumentIndexApproval, chunks: tuple[IndexedDocumentChunk, ...]) -> None:
        with self._connection:
            self._insert(approval, chunks)

    def replace(self, approval, chunks) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM documents WHERE document_id=?", (approval.document_id,))
            self._insert(approval, chunks)

    def document(self, document_id: str):
        return self._connection.execute(
            "SELECT * FROM documents WHERE document_id=?", (document_id,),
        ).fetchone()

    def chunks(self, document_id: str):
        rows = self._connection.execute(
            "SELECT c.*,d.owner_id FROM chunks c JOIN documents d USING(document_id) "
            "WHERE c.document_id=? ORDER BY c.ordinal", (document_id,),
        ).fetchall()
        return [self._decoded_row(row[:6], row[6]) for row in rows]

    def delete(self, document_id: str) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM documents WHERE document_id=?", (document_id,))

    def _insert(self, approval, chunks) -> None:
        scope = approval.scope
        self._connection.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (approval.document_id, approval.source_locator, approval.source_sha256,
             scope.owner_id, json.dumps(scope.purpose_ids), json.dumps(scope.application_ids),
             json.dumps(scope.workspace_ids), scope.session_id, approval.approved_by,
             approval.approved_at.isoformat(), approval.embedding_model_ref,
             approval.embedding_artifact_sha256, approval.contract_version),
        )
        self._connection.executemany(
            "INSERT INTO chunks VALUES (?,?,?,?,?,?)",
            (self._encoded_chunk(scope.owner_id, item) for item in chunks),
        )

    def rows(self):
        rows = self._connection.execute(
            "SELECT c.*,d.source_locator,d.source_sha256,d.owner_id,d.purpose_ids,"
            "d.application_ids,d.workspace_ids,d.session_id,d.embedding_model_ref FROM chunks c "
            "JOIN documents d ON d.document_id=c.document_id ORDER BY c.chunk_id"
        ).fetchall()
        return [self._decoded_row(row, row[8]) for row in rows]

    def _encoded_chunk(self, owner_id, item):
        content, embedding = item.content, json.dumps(item.embedding)
        if self._cipher is not None:
            content = self._cipher.encrypt(owner_id, content.encode())
            embedding = self._cipher.encrypt(owner_id, embedding.encode())
        return item.chunk_id, item.document_id, item.ordinal, content, item.content_sha256, embedding

    def _decoded_row(self, row, owner_id):
        if self._cipher is None:
            return row
        values = list(row)
        values[3] = self._cipher.decrypt(owner_id, values[3]).decode()
        values[5] = self._cipher.decrypt(owner_id, values[5]).decode()
        return tuple(values)

    def close(self) -> None:
        self._connection.close()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents(
 document_id TEXT PRIMARY KEY,source_locator TEXT,source_sha256 TEXT,owner_id TEXT,
 purpose_ids TEXT,application_ids TEXT,workspace_ids TEXT,session_id TEXT,
 approved_by TEXT,approved_at TEXT,embedding_model_ref TEXT,
 embedding_artifact_sha256 TEXT,contract_version TEXT);
CREATE TABLE IF NOT EXISTS chunks(
 chunk_id TEXT PRIMARY KEY,document_id TEXT REFERENCES documents(document_id) ON DELETE CASCADE,
 ordinal INTEGER,content TEXT,content_sha256 TEXT,embedding TEXT);
"""
