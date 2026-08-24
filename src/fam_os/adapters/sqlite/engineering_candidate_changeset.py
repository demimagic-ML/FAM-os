"""Optimistic SQLite persistence for candidate transaction previews."""

import json
import sqlite3
from pathlib import Path
from threading import RLock

from fam_os.core.engineering.candidate_changeset import CandidateChangesetRecord
from fam_os.schemas import SchemaValidationError, dumps_document, loads_document


_ROLLBACK_FIELDS = {
    "rollback_decision": None,
    "rollback_authorization_decision_ids": [],
    "rollback_receipt": None,
}


class SQLiteCandidateChangesetStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._lock = RLock()
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS candidate_changeset ("
            "changeset_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, revision INTEGER NOT NULL, "
            "status TEXT NOT NULL, document TEXT NOT NULL)"
        )
        self._database.commit()

    def begin(self, record):
        with self._lock, self._database:
            try:
                self._database.execute(
                    "INSERT INTO candidate_changeset VALUES (?,?,?,?,?)",
                    (record.changeset_id, record.task_id, record.revision,
                     record.status.value, dumps_document(record)),
                )
            except sqlite3.IntegrityError as error:
                raise RuntimeError("candidate changeset identity already exists") from error

    def load(self, changeset_id):
        with self._lock:
            row = self._database.execute(
                "SELECT document FROM candidate_changeset WHERE changeset_id=?",
                (changeset_id,),
            ).fetchone()
        return None if row is None else _decode(row[0])

    def save(self, expected_revision, record):
        with self._lock, self._database:
            cursor = self._database.execute(
                "UPDATE candidate_changeset SET revision=?,status=?,document=? "
                "WHERE changeset_id=? AND revision=?",
                (record.revision, record.status.value, dumps_document(record),
                 record.changeset_id, expected_revision),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("candidate changeset revision changed concurrently")

    def for_task(self, task_id):
        with self._lock:
            rows = self._database.execute(
                "SELECT document FROM candidate_changeset WHERE task_id=? ORDER BY rowid",
                (task_id,),
            ).fetchall()
        return tuple(_decode(row[0]) for row in rows)

    def close(self):
        with self._lock:
            self._database.close()


def _decode(document):
    try:
        value = loads_document(document)
    except SchemaValidationError:
        value = loads_document(_migrate_pre_rollback_document(document))
    if not isinstance(value, CandidateChangesetRecord):
        raise TypeError("persisted candidate changeset is unexpected")
    return value


def _migrate_pre_rollback_document(serialized: str) -> str:
    """Add only the fields introduced by the explicit rollback state revision."""
    document = json.loads(serialized, object_pairs_hook=_strict_object)
    if (
        not isinstance(document, dict)
        or document.get("schema_id")
        != "fam.core.candidate-changeset/v1alpha1"
        or set(document) != {"schema_id", "contract_version", "payload"}
        or not isinstance(document.get("payload"), dict)
    ):
        raise SchemaValidationError("candidate changeset storage migration is inapplicable")
    payload = document["payload"]
    if set(payload) & set(_ROLLBACK_FIELDS):
        raise SchemaValidationError("candidate changeset rollback fields are incomplete")
    expected = {
        "changeset_id", "definition_id", "task_id", "candidate_id", "preview",
        "operations", "artifacts", "effect_authorization_decision_ids", "status",
        "revision", "created_at", "updated_at", "decision", "receipt",
        "failure_code", "contract_version",
    }
    if set(payload) != expected:
        raise SchemaValidationError("candidate changeset legacy fields do not match")
    payload.update(_ROLLBACK_FIELDS)
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def _strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value
