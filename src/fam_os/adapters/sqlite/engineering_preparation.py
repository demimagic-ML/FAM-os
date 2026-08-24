"""Durable typed engineering preparation records."""

import sqlite3
from pathlib import Path
from threading import RLock

from fam_os.core.engineering.preparation import EngineeringPreparationResult
from fam_os.schemas import dumps_document, loads_document


class SQLiteEngineeringPreparationStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._lock = RLock()
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_preparation ("
            "task_id TEXT PRIMARY KEY, document TEXT NOT NULL, "
            "committed INTEGER NOT NULL DEFAULT 0 CHECK(committed IN (0,1)))"
        )
        columns = {
            row[1] for row in self._database.execute(
                "PRAGMA table_info(engineering_preparation)"
            )
        }
        if "committed" not in columns:
            self._database.execute(
                "ALTER TABLE engineering_preparation "
                "ADD COLUMN committed INTEGER NOT NULL DEFAULT 0"
            )
        self._database.commit()

    def put(self, result: EngineeringPreparationResult) -> None:
        document = dumps_document(result)
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT document FROM engineering_preparation WHERE task_id=?",
                (result.candidate.task_id,),
            ).fetchone()
            if row is not None:
                if row[0] != document:
                    raise RuntimeError("engineering preparation result already exists")
                return
            self._database.execute(
                "INSERT INTO engineering_preparation(task_id, document) VALUES (?,?)",
                (result.candidate.task_id, document),
            )

    def load(self, task_id: str):
        return self._load(task_id, pending_only=False)

    def load_pending(self, task_id: str):
        return self._load(task_id, pending_only=True)

    def _load(self, task_id: str, *, pending_only: bool):
        where = "task_id=? AND committed=0" if pending_only else "task_id=?"
        with self._lock:
            row = self._database.execute(
                f"SELECT document FROM engineering_preparation WHERE {where}",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        value = loads_document(row[0])
        if not isinstance(value, EngineeringPreparationResult):
            raise TypeError("persisted engineering preparation is unexpected")
        return value

    def mark_committed(self, task_id: str, definition_id: str) -> None:
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT document FROM engineering_preparation WHERE task_id=?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("engineering preparation result is unavailable")
            value = loads_document(row[0])
            if (
                not isinstance(value, EngineeringPreparationResult)
                or value.definition_id != definition_id
            ):
                raise RuntimeError("engineering preparation definition is mismatched")
            self._database.execute(
                "UPDATE engineering_preparation SET committed=1 WHERE task_id=?",
                (task_id,),
            )

    def close(self) -> None:
        with self._lock:
            self._database.close()
