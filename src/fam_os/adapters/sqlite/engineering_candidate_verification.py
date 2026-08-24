"""Optimistic SQLite persistence for signed candidate verification."""

import sqlite3
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from threading import RLock

from fam_os.core.engineering.candidate_verification import (
    CandidateVerificationRecord, CandidateVerificationStatus,
)
from fam_os.schemas import dumps_document, loads_document


class SQLiteCandidateVerificationStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._lock = RLock()
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS candidate_verification ("
            "verification_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, "
            "revision INTEGER NOT NULL, status TEXT NOT NULL, document TEXT NOT NULL)"
        )
        self._database.commit()

    def begin(self, record: CandidateVerificationRecord) -> None:
        with self._lock, self._database:
            try:
                self._database.execute(
                    "INSERT INTO candidate_verification VALUES (?,?,?,?,?)",
                    (record.verification_id, record.task_id, record.revision,
                     record.status.value, dumps_document(record)),
                )
            except sqlite3.IntegrityError as error:
                raise RuntimeError("candidate verification identity already exists") from error

    def load(self, verification_id: str):
        with self._lock:
            row = self._database.execute(
                "SELECT document FROM candidate_verification WHERE verification_id=?",
                (verification_id,),
            ).fetchone()
        return None if row is None else _decode(row[0])

    def save(self, expected_revision: int, record: CandidateVerificationRecord) -> None:
        with self._lock, self._database:
            cursor = self._database.execute(
                "UPDATE candidate_verification SET revision=?, status=?, document=? "
                "WHERE verification_id=? AND revision=?",
                (record.revision, record.status.value, dumps_document(record),
                 record.verification_id, expected_revision),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("candidate verification revision changed concurrently")

    def for_task(self, task_id: str) -> tuple[CandidateVerificationRecord, ...]:
        with self._lock:
            rows = self._database.execute(
                "SELECT document FROM candidate_verification WHERE task_id=? ORDER BY rowid",
                (task_id,),
            ).fetchall()
        return tuple(_decode(row[0]) for row in rows)

    def recover_pending(self, instant: datetime) -> int:
        with self._lock:
            rows = self._database.execute(
                "SELECT document FROM candidate_verification WHERE status=?",
                (CandidateVerificationStatus.INTENT_RECORDED.value,),
            ).fetchall()
        records = tuple(_decode(row[0]) for row in rows)
        for record in records:
            self.save(record.revision, replace(
                record, status=CandidateVerificationStatus.RECOVERY_REQUIRED,
                revision=record.revision + 1, updated_at=instant,
                failure_code="restart_interrupted_sandbox_run",
            ))
        return len(records)

    def close(self) -> None:
        with self._lock:
            self._database.close()


def _decode(document):
    value = loads_document(document)
    if not isinstance(value, CandidateVerificationRecord):
        raise TypeError("persisted candidate verification is unexpected")
    return value
