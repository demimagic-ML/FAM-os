"""Durable single-use remote-publication approval consumption."""

import sqlite3
from pathlib import Path


class SQLitePublicationConsumptionStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path)
        self._database.execute("PRAGMA journal_mode=WAL")
        self._database.execute("PRAGMA synchronous=FULL")
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS git_publication_consumption ("
            "approval_id TEXT PRIMARY KEY)"
        )
        self._database.commit()

    def consume_once(self, approval_id: str) -> bool:
        try:
            with self._database:
                self._database.execute(
                    "INSERT INTO git_publication_consumption(approval_id) VALUES (?)",
                    (approval_id,),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def close(self) -> None:
        self._database.close()
