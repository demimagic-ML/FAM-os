"""SQLite WAL persistence for pre-effect candidate generation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock

from fam_os.core.engineering.candidate_generation import (
    GeneratedCandidatePlan, parse_generated_candidate_plan,
)
from fam_os.core.engineering.candidate_generation_record import (
    CandidateGenerationRecord, CandidateGenerationStatus,
)


class SQLiteCandidateGenerationStore:
    def __init__(self, path: Path, codec=None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._database.execute("PRAGMA journal_mode=WAL")
        self._codec = codec
        if codec is not None:
            self._database.execute(
                "CREATE TABLE IF NOT EXISTS engineering_candidate_generations_secure ("
                "generation_id TEXT PRIMARY KEY, status TEXT NOT NULL, "
                "revision INTEGER NOT NULL, record_ciphertext TEXT NOT NULL)"
            )
            if self._legacy_exists():
                self._migrate_legacy_records()
        else:
            self._create_legacy_table()
        self._database.commit()
        self._lock = RLock()

    def load(self, generation_id: str) -> CandidateGenerationRecord | None:
        if self._codec is not None:
            with self._lock:
                row = self._database.execute(
                    "SELECT record_ciphertext FROM "
                    "engineering_candidate_generations_secure WHERE generation_id=?",
                    (generation_id,),
                ).fetchone()
            return None if row is None else self._decode(generation_id, row[0])
        with self._lock:
            row = self._database.execute(
                "SELECT definition_id,task_id,candidate_id,session_id,principal_id,"
                "prompt_sha256,context_sha256,model_ref,status,attempt_count,"
                "consumed_tokens,consumed_wall_seconds,revision,created_at,updated_at,"
                "plan_json,failure_code FROM engineering_candidate_generations "
                "WHERE generation_id=?", (generation_id,),
            ).fetchone()
        return None if row is None else _record(generation_id, row)

    def begin(self, record: CandidateGenerationRecord) -> None:
        if self._codec is not None:
            with self._lock, self._database:
                try:
                    self._database.execute(
                        "INSERT INTO engineering_candidate_generations_secure "
                        "VALUES (?,?,?,?)",
                        (record.generation_id, record.status.value, record.revision,
                         self._codec.encode(record.generation_id, record)),
                    )
                except sqlite3.IntegrityError as error:
                    raise RuntimeError("candidate generation already exists") from error
            return
        with self._lock, self._database:
            try:
                self._database.execute(
                    "INSERT INTO engineering_candidate_generations VALUES "
                    "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    _values(record),
                )
            except sqlite3.IntegrityError as error:
                raise RuntimeError("candidate generation already exists") from error

    def save(self, expected_revision: int, record: CandidateGenerationRecord) -> None:
        if self._codec is not None:
            with self._lock, self._database:
                changed = self._database.execute(
                    "UPDATE engineering_candidate_generations_secure SET "
                    "status=?,revision=?,record_ciphertext=? WHERE generation_id=? "
                    "AND revision=?",
                    (record.status.value, record.revision,
                     self._codec.encode(record.generation_id, record),
                     record.generation_id, expected_revision),
                ).rowcount
            if changed != 1:
                raise RuntimeError("candidate generation revision changed")
            return
        with self._lock, self._database:
            changed = self._database.execute(
                "UPDATE engineering_candidate_generations SET "
                "definition_id=?,task_id=?,candidate_id=?,session_id=?,principal_id=?,"
                "prompt_sha256=?,context_sha256=?,model_ref=?,status=?,attempt_count=?,"
                "consumed_tokens=?,consumed_wall_seconds=?,revision=?,created_at=?,"
                "updated_at=?,plan_json=?,failure_code=? WHERE generation_id=? "
                "AND revision=?",
                (*_values(record)[1:], record.generation_id, expected_revision),
            ).rowcount
        if changed != 1:
            raise RuntimeError("candidate generation revision changed")

    def close(self) -> None:
        with self._lock:
            self._database.close()

    def _decode(self, generation_id, token):
        value = self._codec.decode(generation_id, token)
        if not isinstance(value, CandidateGenerationRecord):
            raise TypeError("encrypted candidate generation is invalid")
        return value

    def _legacy_exists(self) -> bool:
        return self._database.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            ("engineering_candidate_generations",),
        ).fetchone() is not None

    def _create_legacy_table(self) -> None:
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_candidate_generations ("
            "generation_id TEXT PRIMARY KEY, definition_id TEXT NOT NULL, "
            "task_id TEXT NOT NULL, candidate_id TEXT NOT NULL, "
            "session_id TEXT NOT NULL, principal_id TEXT NOT NULL, "
            "prompt_sha256 TEXT NOT NULL, context_sha256 TEXT NOT NULL, "
            "model_ref TEXT NOT NULL, status TEXT NOT NULL, "
            "attempt_count INTEGER NOT NULL, consumed_tokens INTEGER NOT NULL, "
            "consumed_wall_seconds INTEGER NOT NULL, revision INTEGER NOT NULL, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
            "plan_json TEXT, failure_code TEXT)"
        )

    def _migrate_legacy_records(self) -> None:
        self._database.execute("PRAGMA secure_delete=ON")
        rows = self._database.execute(
            "SELECT generation_id,definition_id,task_id,candidate_id,session_id,"
            "principal_id,prompt_sha256,context_sha256,model_ref,status,"
            "attempt_count,consumed_tokens,consumed_wall_seconds,revision,"
            "created_at,updated_at,plan_json,failure_code "
            "FROM engineering_candidate_generations"
        ).fetchall()
        for row in rows:
            record = _record(row[0], row[1:])
            existing = self._database.execute(
                "SELECT record_ciphertext FROM "
                "engineering_candidate_generations_secure WHERE generation_id=?",
                (record.generation_id,),
            ).fetchone()
            if existing is not None and self._decode(
                record.generation_id, existing[0],
            ) != record:
                raise RuntimeError("secure candidate generation migration conflicts")
            if existing is None:
                self._database.execute(
                    "INSERT INTO engineering_candidate_generations_secure VALUES "
                    "(?,?,?,?)",
                    (
                        record.generation_id, record.status.value, record.revision,
                        self._codec.encode(record.generation_id, record),
                    ),
                )
        if rows:
            self._database.execute("DELETE FROM engineering_candidate_generations")


def _values(record):
    return (
        record.generation_id, record.definition_id, record.task_id,
        record.candidate_id, record.session_id, record.principal_id,
        record.prompt_sha256, record.context_sha256, record.model_ref,
        record.status.value, record.attempt_count, record.consumed_tokens,
        record.consumed_wall_seconds, record.revision,
        record.created_at.isoformat(), record.updated_at.isoformat(),
        None if record.plan is None else _plan_json(record.plan),
        record.failure_code,
    )


def _record(generation_id, row):
    from datetime import datetime
    plan = None if row[15] is None else parse_generated_candidate_plan(
        row[15], maximum_operations=512, maximum_content_bytes=64 * 1024**2,
    )
    return CandidateGenerationRecord(
        generation_id, *row[:8], CandidateGenerationStatus(row[8]),
        *row[9:13], datetime.fromisoformat(row[13]), datetime.fromisoformat(row[14]),
        plan, row[16],
    )


def _plan_json(plan: GeneratedCandidatePlan) -> str:
    value = {
        "contract_version": plan.contract_version,
        "summary": plan.summary,
        "operations": [
            {
                "kind": item.kind.value, "path": item.path,
                "content": item.content, "source_path": item.source_path,
                "media_type": item.media_type,
            }
            for item in plan.operations
        ],
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
