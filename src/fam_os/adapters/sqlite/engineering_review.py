"""Optimistically revisioned SQLite engineering review store."""

import sqlite3
from pathlib import Path
from threading import RLock

from fam_os.core.engineering.review import (
    EngineeringReviewCheckpoint,
    EngineeringReviewResolutionReceipt,
    EngineeringReviewSelection,
    EngineeringReviewWaiverDecision,
)
from fam_os.schemas import dumps_document, loads_document


class SQLiteEngineeringReviewStore:
    def __init__(self, path: Path, codec=None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._lock = RLock()
        self._codec = codec
        self._database.execute("PRAGMA journal_mode=WAL")
        self._database.execute("PRAGMA synchronous=FULL")
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_reviews ("
            "checkpoint_id TEXT PRIMARY KEY, task_id TEXT, "
            "revision INTEGER NOT NULL, document TEXT NOT NULL)"
        )
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_review_evidence ("
            "evidence_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, "
            "evidence_kind TEXT NOT NULL, document TEXT NOT NULL)"
        )
        columns = {
            row[1] for row in self._database.execute(
                "PRAGMA table_info(engineering_reviews)"
            ).fetchall()
        }
        if "task_id" not in columns:
            self._database.execute(
                "ALTER TABLE engineering_reviews ADD COLUMN task_id TEXT"
            )
        self._migrate_records()
        self._database.execute(
            "CREATE INDEX IF NOT EXISTS engineering_reviews_task_id "
            "ON engineering_reviews(task_id)"
        )
        self._database.execute(
            "CREATE INDEX IF NOT EXISTS engineering_review_evidence_task_id "
            "ON engineering_review_evidence(task_id)"
        )
        self._database.commit()

    def load(self, checkpoint_id: str):
        with self._lock:
            row = self._database.execute(
                "SELECT document FROM engineering_reviews WHERE checkpoint_id=?",
                (checkpoint_id,),
            ).fetchone()
        if row is None:
            return None
        return self._decode(checkpoint_id, row[0])

    def for_task(self, task_id: str):
        with self._lock:
            rows = self._database.execute(
                "SELECT checkpoint_id,document FROM engineering_reviews "
                "WHERE task_id=? ORDER BY checkpoint_id", (task_id,),
            ).fetchall()
        return tuple(self._decode(row[0], row[1]) for row in rows)

    def save(self, expected_revision, checkpoint) -> None:
        document = self._encode(checkpoint)
        with self._lock, self._database:
            if expected_revision == -1:
                try:
                    self._database.execute(
                        "INSERT INTO engineering_reviews "
                        "(checkpoint_id,task_id,revision,document) VALUES (?,?,?,?)",
                        (
                            checkpoint.checkpoint_id, checkpoint.task_id,
                            checkpoint.revision, document,
                        ),
                    )
                except sqlite3.IntegrityError as error:
                    raise RuntimeError("engineering review already exists") from error
            else:
                cursor = self._database.execute(
                    "UPDATE engineering_reviews SET task_id=?,revision=?,document=? "
                    "WHERE checkpoint_id=? AND revision=?",
                    (
                        checkpoint.task_id, checkpoint.revision, document,
                        checkpoint.checkpoint_id, expected_revision,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("engineering review revision is stale")

    def save_evidence(self, value, *, task_id: str | None = None) -> None:
        evidence_id, inferred_task_id, kind = _evidence_identity(value)
        task_id = inferred_task_id or task_id
        if not task_id:
            raise ValueError("engineering review evidence requires a task identity")
        document = self._encode_value(evidence_id, value)
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT task_id,evidence_kind,document "
                "FROM engineering_review_evidence WHERE evidence_id=?",
                (evidence_id,),
            ).fetchone()
            if row is None:
                self._database.execute(
                    "INSERT INTO engineering_review_evidence "
                    "(evidence_id,task_id,evidence_kind,document) VALUES (?,?,?,?)",
                    (evidence_id, task_id, kind, document),
                )
            elif row != (task_id, kind, document):
                raise RuntimeError("engineering review evidence identity conflicts")

    def load_evidence(self, evidence_id: str):
        with self._lock:
            row = self._database.execute(
                "SELECT document FROM engineering_review_evidence "
                "WHERE evidence_id=?", (evidence_id,),
            ).fetchone()
        return None if row is None else self._decode_value(evidence_id, row[0])

    def evidence_for_task(self, task_id: str):
        with self._lock:
            rows = self._database.execute(
                "SELECT evidence_id,document FROM engineering_review_evidence "
                "WHERE task_id=? ORDER BY evidence_id", (task_id,),
            ).fetchall()
        return tuple(self._decode_value(row[0], row[1]) for row in rows)

    def close(self) -> None:
        with self._lock:
            self._database.close()

    def _encode(self, checkpoint: EngineeringReviewCheckpoint) -> str:
        return self._encode_value(checkpoint.checkpoint_id, checkpoint)

    def _decode(self, checkpoint_id: str, document: str):
        value = self._decode_value(checkpoint_id, document)
        if not isinstance(value, EngineeringReviewCheckpoint):
            raise TypeError("persisted engineering review has an unexpected contract")
        return value

    def _encode_value(self, identity: str, value) -> str:
        if self._codec is None:
            return dumps_document(value)
        return self._codec.encode(identity, value)

    def _decode_value(self, identity: str, document: str):
        value = (
            loads_document(document)
            if self._codec is None
            else self._codec.decode(identity, document)
        )
        if not isinstance(value, _EVIDENCE_TYPES):
            raise TypeError("persisted engineering review evidence has an unexpected contract")
        return value

    def _migrate_records(self) -> None:
        rows = self._database.execute(
            "SELECT checkpoint_id,task_id,document FROM engineering_reviews"
        ).fetchall()
        for checkpoint_id, task_id, document in rows:
            if self._codec is not None and document.lstrip().startswith("{"):
                value = loads_document(document)
                if not isinstance(value, EngineeringReviewCheckpoint):
                    raise TypeError(
                        "persisted engineering review has an unexpected contract"
                    )
                document = self._codec.encode(checkpoint_id, value)
            else:
                value = self._decode(checkpoint_id, document)
            if task_id is not None and task_id != value.task_id:
                raise RuntimeError("persisted engineering review task differs")
            self._database.execute(
                "UPDATE engineering_reviews SET task_id=?,document=? "
                "WHERE checkpoint_id=?",
                (value.task_id, document, checkpoint_id),
            )


_EVIDENCE_TYPES = (
    EngineeringReviewCheckpoint,
    EngineeringReviewResolutionReceipt,
    EngineeringReviewSelection,
    EngineeringReviewWaiverDecision,
)


def _evidence_identity(value):
    if isinstance(value, EngineeringReviewSelection):
        return value.selection_id, value.task_id, "selection"
    if isinstance(value, EngineeringReviewResolutionReceipt):
        return value.receipt_id, value.task_id, "resolution"
    if isinstance(value, EngineeringReviewWaiverDecision):
        return value.decision_id, None, "waiver"
    raise TypeError("engineering review evidence type is unsupported")
