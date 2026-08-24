"""Immutable indexed storage for governed engineering documentation records."""

import sqlite3
from pathlib import Path
from threading import RLock

from fam_os.core.engineering import (
    DocumentationGenerationRequest, DocumentationGovernanceBinding,
    DocumentationRequirementSelection, DocumentationStalenessReport,
    GeneratedDocumentationReceipt, RequirementTraceabilityRecord,
)
from fam_os.schemas import dumps_document, loads_document


_TYPES = (
    DocumentationGenerationRequest, DocumentationGovernanceBinding,
    DocumentationRequirementSelection,
    GeneratedDocumentationReceipt,
    DocumentationStalenessReport, RequirementTraceabilityRecord,
)


class SQLiteEngineeringDocumentationStore:
    def __init__(self, path: Path, codec=None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._database.execute("PRAGMA journal_mode=WAL")
        self._database.execute("PRAGMA synchronous=FULL")
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_documentation ("
            "record_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, "
            "record_kind TEXT NOT NULL, document TEXT NOT NULL)"
        )
        self._database.execute(
            "CREATE INDEX IF NOT EXISTS engineering_documentation_task_id "
            "ON engineering_documentation(task_id)"
        )
        self._database.commit()
        self._codec = codec
        self._lock = RLock()

    def put(self, value) -> None:
        record_id, task_id, kind = _identity(value)
        document = self._encode(record_id, value)
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT document FROM engineering_documentation WHERE record_id=?",
                (record_id,),
            ).fetchone()
            if row is not None:
                if self._decode(record_id, row[0]) != value:
                    raise RuntimeError("engineering documentation record differs")
                return
            self._database.execute(
                "INSERT INTO engineering_documentation VALUES (?,?,?,?)",
                (record_id, task_id, kind, document),
            )

    def load(self, record_id: str):
        with self._lock:
            row = self._database.execute(
                "SELECT document FROM engineering_documentation WHERE record_id=?",
                (record_id,),
            ).fetchone()
        return None if row is None else self._decode(record_id, row[0])

    def for_task(self, task_id: str):
        with self._lock:
            rows = self._database.execute(
                "SELECT record_id,document FROM engineering_documentation "
                "WHERE task_id=? ORDER BY record_kind,record_id", (task_id,),
            ).fetchall()
        return tuple(self._decode(row[0], row[1]) for row in rows)

    def close(self) -> None:
        with self._lock:
            self._database.close()

    def _encode(self, record_id, value) -> str:
        if self._codec is None:
            return dumps_document(value)
        return self._codec.encode(record_id, value)

    def _decode(self, record_id, document):
        value = (
            loads_document(document)
            if self._codec is None
            else self._codec.decode(record_id, document)
        )
        if not isinstance(value, _TYPES):
            raise TypeError("persisted engineering documentation is unexpected")
        return value


def _identity(value):
    if isinstance(value, DocumentationGenerationRequest):
        return value.request_id, value.task_id, "request"
    if isinstance(value, DocumentationRequirementSelection):
        return value.selection_id, value.task_id, "selection"
    if isinstance(value, DocumentationGovernanceBinding):
        return value.binding_id, value.task_id, "governance"
    if isinstance(value, GeneratedDocumentationReceipt):
        return value.receipt_id, value.task_id, "receipt"
    if isinstance(value, DocumentationStalenessReport):
        return value.report_id, value.task_id, "staleness"
    if isinstance(value, RequirementTraceabilityRecord):
        return value.trace_id, value.task_id, "trace"
    raise TypeError("engineering documentation record type is unsupported")
