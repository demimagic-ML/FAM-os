"""Optimistic SQLite persistence for candidate edit intents and receipts."""

import sqlite3
from pathlib import Path
from threading import RLock

from fam_os.core.engineering.candidate_edit import CandidateEditRecord, CandidateEditStatus
from fam_os.schemas import dumps_document, loads_document


class SQLiteCandidateEditStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._lock = RLock()
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS candidate_edit ("
            "edit_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, revision INTEGER NOT NULL, "
            "status TEXT NOT NULL, changed_bytes INTEGER NOT NULL, document TEXT NOT NULL)"
        )
        self._database.commit()

    def load(self, edit_id: str):
        with self._lock:
            row = self._database.execute(
                "SELECT document FROM candidate_edit WHERE edit_id=?", (edit_id,),
            ).fetchone()
        return None if row is None else _decode(row[0])

    def begin(self, record: CandidateEditRecord) -> None:
        with self._lock, self._database:
            try:
                self._database.execute(
                    "INSERT INTO candidate_edit VALUES (?,?,?,?,?,?)",
                    (record.edit_id, record.task_id, record.revision,
                     record.status.value, record.changed_bytes, dumps_document(record)),
                )
            except sqlite3.IntegrityError as error:
                raise RuntimeError("candidate edit identity already exists") from error

    def save(self, expected_revision: int, record: CandidateEditRecord) -> None:
        with self._lock, self._database:
            cursor = self._database.execute(
                "UPDATE candidate_edit SET revision=?, status=?, document=? "
                "WHERE edit_id=? AND revision=?",
                (record.revision, record.status.value, dumps_document(record),
                 record.edit_id, expected_revision),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("candidate edit revision changed concurrently")

    def usage(self, task_id: str) -> tuple[int, int]:
        with self._lock:
            row = self._database.execute(
                "SELECT COUNT(*), COALESCE(SUM(changed_bytes),0) FROM candidate_edit "
                "WHERE task_id=? AND status IN (?,?)",
                (task_id, CandidateEditStatus.INTENT_RECORDED.value,
                 CandidateEditStatus.APPLIED.value),
            ).fetchone()
        return int(row[0]), int(row[1])

    def for_task(self, task_id: str) -> tuple[CandidateEditRecord, ...]:
        with self._lock:
            rows = self._database.execute(
                "SELECT document FROM candidate_edit WHERE task_id=? ORDER BY rowid",
                (task_id,),
            ).fetchall()
        return tuple(_decode(row[0]) for row in rows)

    def close(self) -> None:
        with self._lock:
            self._database.close()


def _decode(document: str) -> CandidateEditRecord:
    value = loads_document(document)
    if not isinstance(value, CandidateEditRecord):
        raise TypeError("persisted candidate edit is unexpected")
    return value
