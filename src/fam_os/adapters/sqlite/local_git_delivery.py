"""Optimistic SQLite WAL storage for local Git delivery intents."""

import sqlite3
from pathlib import Path
from threading import RLock

from fam_os.core.engineering.local_git_delivery import LocalGitDeliveryRecord
from fam_os.schemas import dumps_document, loads_document


class SQLiteLocalGitDeliveryStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._database.execute("PRAGMA journal_mode=WAL")
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_local_git_delivery ("
            "delivery_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, "
            "revision INTEGER NOT NULL, status TEXT NOT NULL, document TEXT NOT NULL)"
        )
        self._database.commit()
        self._lock = RLock()

    def load(self, delivery_id):
        with self._lock:
            row = self._database.execute(
                "SELECT document FROM engineering_local_git_delivery WHERE delivery_id=?",
                (delivery_id,),
            ).fetchone()
        return None if row is None else _decode(row[0])

    def begin(self, record):
        with self._lock, self._database:
            try:
                self._database.execute(
                    "INSERT INTO engineering_local_git_delivery VALUES (?,?,?,?,?)",
                    (record.delivery_id, record.task_id, record.revision,
                     record.status.value, dumps_document(record)),
                )
            except sqlite3.IntegrityError as error:
                raise RuntimeError("local Git delivery already exists") from error

    def save(self, expected_revision, record):
        with self._lock, self._database:
            changed = self._database.execute(
                "UPDATE engineering_local_git_delivery SET revision=?,status=?,document=? "
                "WHERE delivery_id=? AND revision=?",
                (record.revision, record.status.value, dumps_document(record),
                 record.delivery_id, expected_revision),
            ).rowcount
        if changed != 1:
            raise RuntimeError("local Git delivery revision changed")

    def close(self):
        with self._lock:
            self._database.close()


def _decode(document):
    value = loads_document(document)
    if not isinstance(value, LocalGitDeliveryRecord):
        raise TypeError("persisted local Git delivery is unexpected")
    return value
