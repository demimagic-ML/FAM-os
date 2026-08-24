"""Immutable owner-scoped SQLite runtime-diagnostic evidence store."""

import sqlite3
from pathlib import Path
from threading import RLock

from fam_os.core.engineering.diagnostics import (
    RuntimeDiagnosticReceipt, RuntimeDiagnosticRequest,
)
from fam_os.schemas import dumps_document, loads_document


class SQLiteRuntimeDiagnosticStore:
    def __init__(self, path: Path, codec=None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._lock = RLock()
        self._codec = codec
        self._database.execute("PRAGMA journal_mode=WAL")
        self._database.execute("PRAGMA synchronous=FULL")
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_runtime_diagnostics ("
            "request_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, "
            "request_document TEXT NOT NULL, receipt_id TEXT, "
            "receipt_document TEXT)"
        )
        self._database.execute(
            "CREATE INDEX IF NOT EXISTS engineering_runtime_diagnostics_task "
            "ON engineering_runtime_diagnostics(task_id)"
        )
        self._database.commit()

    def put_request(self, request: RuntimeDiagnosticRequest) -> None:
        document = self._encode(request.request_id, request)
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT task_id,request_document FROM "
                "engineering_runtime_diagnostics WHERE request_id=?",
                (request.request_id,),
            ).fetchone()
            expected = request.task_id, document
            if row is None:
                self._database.execute(
                    "INSERT INTO engineering_runtime_diagnostics "
                    "(request_id,task_id,request_document) VALUES (?,?,?)",
                    (request.request_id, request.task_id, document),
                )
            elif row != expected:
                raise RuntimeError("runtime diagnostic request identity conflicts")

    def load_request(self, request_id: str):
        with self._lock:
            row = self._database.execute(
                "SELECT request_document FROM engineering_runtime_diagnostics "
                "WHERE request_id=?", (request_id,),
            ).fetchone()
        if row is None:
            return None
        return self._decode(request_id, row[0], RuntimeDiagnosticRequest)

    def put_receipt(self, receipt: RuntimeDiagnosticReceipt) -> None:
        document = self._encode(receipt.receipt_id, receipt)
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT task_id,receipt_id,receipt_document FROM "
                "engineering_runtime_diagnostics WHERE request_id=?",
                (receipt.request_id,),
            ).fetchone()
            if row is None or row[0] != receipt.task_id:
                raise KeyError("runtime diagnostic request is unavailable")
            expected = receipt.receipt_id, document
            if row[1] is None:
                self._database.execute(
                    "UPDATE engineering_runtime_diagnostics SET "
                    "receipt_id=?,receipt_document=? WHERE request_id=?",
                    (receipt.receipt_id, document, receipt.request_id),
                )
            elif row[1:] != expected:
                raise RuntimeError("runtime diagnostic receipt identity conflicts")

    def load_receipt(self, request_id: str):
        with self._lock:
            row = self._database.execute(
                "SELECT receipt_id,receipt_document FROM "
                "engineering_runtime_diagnostics WHERE request_id=?",
                (request_id,),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return self._decode(row[0], row[1], RuntimeDiagnosticReceipt)

    def requests_for_task(self, task_id: str):
        with self._lock:
            rows = self._database.execute(
                "SELECT request_id,request_document FROM "
                "engineering_runtime_diagnostics WHERE task_id=? "
                "ORDER BY request_id", (task_id,),
            ).fetchall()
        return tuple(
            self._decode(identity, document, RuntimeDiagnosticRequest)
            for identity, document in rows
        )

    def receipts_for_task(self, task_id: str):
        with self._lock:
            rows = self._database.execute(
                "SELECT receipt_id,receipt_document FROM "
                "engineering_runtime_diagnostics WHERE task_id=? "
                "AND receipt_id IS NOT NULL ORDER BY request_id", (task_id,),
            ).fetchall()
        return tuple(
            self._decode(identity, document, RuntimeDiagnosticReceipt)
            for identity, document in rows
        )

    def close(self) -> None:
        with self._lock:
            self._database.close()

    def _encode(self, identity: str, value) -> str:
        if self._codec is None:
            return dumps_document(value)
        return self._codec.encode(identity, value)

    def _decode(self, identity: str, document: str, expected):
        value = (
            loads_document(document)
            if self._codec is None else self._codec.decode(identity, document)
        )
        if not isinstance(value, expected):
            raise TypeError("persisted runtime diagnostic has an unexpected contract")
        return value
