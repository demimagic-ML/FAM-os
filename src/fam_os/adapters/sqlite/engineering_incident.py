"""Optimistic SQLite persistence for engineering incidents."""

import sqlite3
from pathlib import Path
from threading import RLock

from fam_os.core.engineering.incident import (
    EngineeringIncidentEvidenceReceipt, EngineeringIncidentState,
)
from fam_os.schemas import dumps_document, loads_document


class SQLiteEngineeringIncidentStore:
    def __init__(self, path: Path, codec=None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._database.execute("PRAGMA journal_mode=WAL")
        self._database.execute("PRAGMA synchronous=FULL")
        self._lock = RLock()
        self._codec = codec
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_incidents ("
            "incident_id TEXT PRIMARY KEY, task_id TEXT, "
            "revision INTEGER NOT NULL, document TEXT NOT NULL)"
        )
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_incident_receipts ("
            "receipt_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, "
            "task_id TEXT NOT NULL, document TEXT NOT NULL)"
        )
        self._database.execute(
            "CREATE INDEX IF NOT EXISTS engineering_incident_receipts_incident "
            "ON engineering_incident_receipts(incident_id)"
        )
        columns = {
            row[1] for row in self._database.execute(
                "PRAGMA table_info(engineering_incidents)"
            ).fetchall()
        }
        if "task_id" not in columns:
            self._database.execute(
                "ALTER TABLE engineering_incidents ADD COLUMN task_id TEXT"
        )
        self._migrate_records()
        self._migrate_receipts()
        self._database.execute(
            "CREATE INDEX IF NOT EXISTS engineering_incidents_task_id "
            "ON engineering_incidents(task_id)"
        )
        self._database.commit()

    def load(self, incident_id):
        with self._lock:
            row = self._database.execute(
                "SELECT document FROM engineering_incidents WHERE incident_id=?",
                (incident_id,),
            ).fetchone()
        if row is None:
            return None
        return self._decode_state(incident_id, row[0])

    def for_task(self, task_id):
        with self._lock:
            rows = self._database.execute(
                "SELECT incident_id,document FROM engineering_incidents "
                "WHERE task_id=? "
                "ORDER BY incident_id"
                , (task_id,),
            ).fetchall()
        values = tuple(self._decode_state(row[0], row[1]) for row in rows)
        return tuple(sorted(
            values, key=lambda item: (item.detected_at, item.incident_id),
        ))

    def put_receipt(self, receipt):
        document = self._encode(receipt.receipt_id, receipt)
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT document FROM engineering_incident_receipts "
                "WHERE receipt_id=?", (receipt.receipt_id,),
            ).fetchone()
            if row is not None:
                if self._decode_receipt(receipt.receipt_id, row[0]) != receipt:
                    raise RuntimeError("engineering incident receipt differs")
                return
            self._database.execute(
                "INSERT INTO engineering_incident_receipts VALUES (?,?,?,?)",
                (
                    receipt.receipt_id, receipt.incident_id, receipt.task_id,
                    document,
                ),
            )

    def load_receipt(self, receipt_id):
        with self._lock:
            row = self._database.execute(
                "SELECT document FROM engineering_incident_receipts "
                "WHERE receipt_id=?", (receipt_id,),
            ).fetchone()
        return None if row is None else self._decode_receipt(receipt_id, row[0])

    def receipts_for_incident(self, incident_id):
        with self._lock:
            rows = self._database.execute(
                "SELECT receipt_id,document FROM engineering_incident_receipts "
                "WHERE incident_id=? ORDER BY rowid", (incident_id,),
            ).fetchall()
        return tuple(self._decode_receipt(row[0], row[1]) for row in rows)

    def save(self, expected_revision, state):
        document = self._encode(state.incident_id, state)
        with self._lock, self._database:
            if expected_revision == -1:
                try:
                    self._database.execute(
                        "INSERT INTO engineering_incidents "
                        "(incident_id,task_id,revision,document) VALUES (?,?,?,?)",
                        (state.incident_id, state.task_id, state.revision, document),
                    )
                except sqlite3.IntegrityError as error:
                    raise RuntimeError("engineering incident already exists") from error
            else:
                cursor = self._database.execute(
                    "UPDATE engineering_incidents SET task_id=?,revision=?,document=? "
                    "WHERE incident_id=? AND revision=?",
                    (
                        state.task_id, state.revision, document,
                        state.incident_id, expected_revision,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("engineering incident revision is stale")

    def close(self):
        with self._lock:
            self._database.close()

    def _encode(self, identity, value) -> str:
        if self._codec is None:
            return dumps_document(value)
        return self._codec.encode(identity, value)

    def _decode(self, identity: str, document: str):
        value = (
            loads_document(document)
            if self._codec is None
            else self._codec.decode(identity, document)
        )
        return value

    def _decode_state(self, incident_id, document) -> EngineeringIncidentState:
        value = self._decode(incident_id, document)
        if not isinstance(value, EngineeringIncidentState):
            raise TypeError("persisted engineering incident has an unexpected contract")
        return value

    def _decode_receipt(
        self, receipt_id, document,
    ) -> EngineeringIncidentEvidenceReceipt:
        value = self._decode(receipt_id, document)
        if not isinstance(value, EngineeringIncidentEvidenceReceipt):
            raise TypeError("persisted engineering incident receipt is unexpected")
        return value

    def _migrate_records(self) -> None:
        rows = self._database.execute(
            "SELECT incident_id,task_id,document FROM engineering_incidents"
        ).fetchall()
        for incident_id, task_id, document in rows:
            if self._codec is not None and document.lstrip().startswith("{"):
                value = loads_document(document)
                if not isinstance(value, EngineeringIncidentState):
                    raise TypeError(
                        "persisted engineering incident has an unexpected contract"
                    )
                document = self._codec.encode(incident_id, value)
            else:
                value = self._decode_state(incident_id, document)
            if task_id is not None and task_id != value.task_id:
                raise RuntimeError("persisted engineering incident task differs")
            self._database.execute(
                "UPDATE engineering_incidents SET task_id=?,document=? "
                "WHERE incident_id=?",
                (value.task_id, document, incident_id),
            )

    def _migrate_receipts(self) -> None:
        rows = self._database.execute(
            "SELECT receipt_id,incident_id,task_id,document "
            "FROM engineering_incident_receipts"
        ).fetchall()
        for receipt_id, incident_id, task_id, document in rows:
            if self._codec is not None and document.lstrip().startswith("{"):
                value = loads_document(document)
                if not isinstance(value, EngineeringIncidentEvidenceReceipt):
                    raise TypeError(
                        "persisted engineering incident receipt is unexpected"
                    )
                document = self._codec.encode(receipt_id, value)
            else:
                value = self._decode_receipt(receipt_id, document)
            if value.incident_id != incident_id or value.task_id != task_id:
                raise RuntimeError("persisted engineering incident receipt differs")
            self._database.execute(
                "UPDATE engineering_incident_receipts SET document=? "
                "WHERE receipt_id=?", (document, receipt_id),
            )
