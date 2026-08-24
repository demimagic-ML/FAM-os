"""Optimistically revisioned durable engineering-loop state."""

import sqlite3
from pathlib import Path
from threading import RLock

from fam_os.core.engineering.master_loop import EngineeringLoopState
from fam_os.core.engineering.task_definition import EngineeringTaskDefinition
from fam_os.schemas import dumps_document, loads_document


class SQLiteEngineeringLoopStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._lock = RLock()
        self._database.execute("PRAGMA journal_mode=WAL")
        self._database.execute("PRAGMA synchronous=FULL")
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_loop_state ("
            "task_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, document TEXT NOT NULL)"
        )
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_task_definition ("
            "task_id TEXT PRIMARY KEY, document TEXT NOT NULL)"
        )
        self._database.commit()

    def load(self, task_id: str) -> EngineeringLoopState | None:
        with self._lock:
            row = self._database.execute(
                "SELECT document FROM engineering_loop_state WHERE task_id = ?", (task_id,),
            ).fetchone()
        if row is None:
            return None
        value = loads_document(row[0])
        if not isinstance(value, EngineeringLoopState):
            raise TypeError("persisted engineering loop has an unexpected contract")
        return value

    def states(self) -> tuple[EngineeringLoopState, ...]:
        with self._lock:
            rows = self._database.execute(
                "SELECT document FROM engineering_loop_state ORDER BY task_id"
            ).fetchall()
        values = tuple(loads_document(row[0]) for row in rows)
        if not all(isinstance(value, EngineeringLoopState) for value in values):
            raise TypeError("persisted engineering loop has an unexpected contract")
        return values

    def save(self, expected_revision: int, state: EngineeringLoopState) -> None:
        document = dumps_document(state)
        with self._lock, self._database:
            if expected_revision == -1:
                try:
                    self._database.execute(
                        "INSERT INTO engineering_loop_state(task_id, revision, document) VALUES (?, ?, ?)",
                        (state.task_id, state.revision, document),
                    )
                except sqlite3.IntegrityError as error:
                    raise RuntimeError("engineering loop state already exists") from error
            else:
                cursor = self._database.execute(
                    "UPDATE engineering_loop_state SET revision = ?, document = ? "
                    "WHERE task_id = ? AND revision = ?",
                    (state.revision, document, state.task_id, expected_revision),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("engineering loop state revision is stale")

    def start_task(
        self, definition: EngineeringTaskDefinition, state: EngineeringLoopState,
    ) -> None:
        if definition.task.task_id != state.task_id or definition.task.grant_id != state.grant_id:
            raise ValueError("engineering task definition and state are mismatched")
        state_document = dumps_document(state)
        definition_document = dumps_document(definition)
        with self._lock, self._database:
            try:
                self._database.execute(
                    "INSERT INTO engineering_task_definition VALUES (?,?)",
                    (state.task_id, definition_document),
                )
                self._database.execute(
                    "INSERT INTO engineering_loop_state(task_id,revision,document) VALUES (?,?,?)",
                    (state.task_id, state.revision, state_document),
                )
            except sqlite3.IntegrityError as error:
                raise RuntimeError("engineering task already exists") from error

    def load_task(self, task_id: str) -> EngineeringTaskDefinition | None:
        with self._lock:
            row = self._database.execute(
                "SELECT document FROM engineering_task_definition WHERE task_id=?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        value = loads_document(row[0])
        if not isinstance(value, EngineeringTaskDefinition):
            raise TypeError("persisted engineering task definition is unexpected")
        return value

    def close(self) -> None:
        with self._lock:
            self._database.close()
