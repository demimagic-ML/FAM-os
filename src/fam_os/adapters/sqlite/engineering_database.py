"""Immutable owner-scoped persistence for database plans and outcomes."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from fam_os.adapters.database import SQLiteEngineeringResult
from fam_os.core.engineering import (
    DatabaseBackupReceipt, DatabaseChangePlan, DatabasePostapplyReceipt,
    DatabaseVerificationReceipt,
)
from fam_os.schemas import dumps_document, loads_document


@dataclass(frozen=True, slots=True)
class StoredDatabaseEngineeringResult:
    plan: DatabaseChangePlan
    backup: DatabaseBackupReceipt | None
    verification: DatabaseVerificationReceipt
    backup_relative_path: str | None
    failure_code: str | None

    def __post_init__(self) -> None:
        if (
            self.verification.plan_id != self.plan.plan_id
            or self.verification.target_id != self.plan.target.target_id
        ):
            raise ValueError("stored database result identities are inconsistent")
        if self.backup is not None and (
            self.backup.plan_id != self.plan.plan_id
            or self.backup.target_id != self.plan.target.target_id
            or self.verification.backup_id != self.backup.backup_id
        ):
            raise ValueError("stored database backup identities are inconsistent")
        if (self.backup is None) != (self.backup_relative_path is None):
            raise ValueError("stored database backup path is inconsistent")
        if self.failure_code is not None and not self.failure_code.strip():
            raise ValueError("stored database failure code must be nonempty")


class SQLiteDatabaseEngineeringStore:
    def __init__(self, path: Path, codec=None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._database = sqlite3.connect(path, check_same_thread=False)
        self._lock = RLock()
        self._codec = codec
        self._database.execute("PRAGMA journal_mode=WAL")
        self._database.execute("PRAGMA synchronous=FULL")
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_database ("
            "plan_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, "
            "candidate_id TEXT NOT NULL, plan_document TEXT NOT NULL, "
            "backup_id TEXT, backup_document TEXT, backup_relative_path TEXT, "
            "verification_id TEXT, verification_document TEXT, failure_code TEXT)"
        )
        self._database.execute(
            "CREATE INDEX IF NOT EXISTS engineering_database_task "
            "ON engineering_database(task_id,plan_id)"
        )
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS engineering_database_postapply ("
            "receipt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, "
            "plan_id TEXT NOT NULL UNIQUE, document TEXT NOT NULL)"
        )
        self._database.commit()

    def put_plan(self, plan: DatabaseChangePlan) -> None:
        document = self._encode(plan.plan_id, plan)
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT task_id,candidate_id,plan_document FROM "
                "engineering_database WHERE plan_id=?", (plan.plan_id,),
            ).fetchone()
            expected = plan.task_id, plan.candidate_id, document
            if row is None:
                self._database.execute(
                    "INSERT INTO engineering_database "
                    "(plan_id,task_id,candidate_id,plan_document) VALUES (?,?,?,?)",
                    (plan.plan_id, *expected),
                )
            elif row != expected:
                raise RuntimeError("database plan identity conflicts")

    def put_success(self, plan_id: str, result: SQLiteEngineeringResult) -> None:
        self._put_result(
            plan_id, result.backup, result.verification,
            result.backup_relative_path, None,
        )

    def put_recovery(
        self, plan_id: str, verification: DatabaseVerificationReceipt,
        failure_code: str,
    ) -> None:
        self._put_result(plan_id, None, verification, None, failure_code)

    def load_plan(self, plan_id: str):
        with self._lock:
            row = self._database.execute(
                "SELECT plan_document FROM engineering_database WHERE plan_id=?",
                (plan_id,),
            ).fetchone()
        return None if row is None else self._decode(
            plan_id, row[0], DatabaseChangePlan,
        )

    def load_result(self, plan_id: str):
        with self._lock:
            row = self._database.execute(
                "SELECT plan_document,backup_id,backup_document,"
                "backup_relative_path,verification_id,verification_document,"
                "failure_code FROM engineering_database WHERE plan_id=?",
                (plan_id,),
            ).fetchone()
        if row is None or row[4] is None:
            return None
        plan = self._decode(plan_id, row[0], DatabaseChangePlan)
        backup = (
            None if row[1] is None else
            self._decode(row[1], row[2], DatabaseBackupReceipt)
        )
        verification = self._decode(
            row[4], row[5], DatabaseVerificationReceipt,
        )
        return StoredDatabaseEngineeringResult(
            plan, backup, verification, row[3], row[6],
        )

    def plans_for_task(self, task_id: str):
        with self._lock:
            rows = self._database.execute(
                "SELECT plan_id,plan_document FROM engineering_database "
                "WHERE task_id=? ORDER BY plan_id", (task_id,),
            ).fetchall()
        return tuple(
            self._decode(identity, document, DatabaseChangePlan)
            for identity, document in rows
        )

    def results_for_task(self, task_id: str):
        return tuple(
            result for plan in self.plans_for_task(task_id)
            if (result := self.load_result(plan.plan_id)) is not None
        )

    def put_postapply(self, receipt: DatabasePostapplyReceipt) -> None:
        document = self._encode(receipt.receipt_id, receipt)
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT task_id,plan_id,document FROM "
                "engineering_database_postapply WHERE receipt_id=?",
                (receipt.receipt_id,),
            ).fetchone()
            expected = receipt.task_id, receipt.plan_id, document
            if row is None:
                try:
                    self._database.execute(
                        "INSERT INTO engineering_database_postapply "
                        "VALUES (?,?,?,?)", (receipt.receipt_id, *expected),
                    )
                except sqlite3.IntegrityError as error:
                    raise RuntimeError(
                        "database post-apply plan already has evidence"
                    ) from error
            elif row != expected:
                raise RuntimeError("database post-apply receipt identity conflicts")

    def postapply_for_task(self, task_id: str):
        with self._lock:
            rows = self._database.execute(
                "SELECT receipt_id,document FROM engineering_database_postapply "
                "WHERE task_id=? ORDER BY receipt_id", (task_id,),
            ).fetchall()
        return tuple(
            self._decode(identity, document, DatabasePostapplyReceipt)
            for identity, document in rows
        )

    def close(self) -> None:
        with self._lock:
            self._database.close()

    def _put_result(self, plan_id, backup, verification, relative, failure):
        with self._lock, self._database:
            row = self._database.execute(
                "SELECT task_id,backup_id,backup_document,backup_relative_path,"
                "verification_id,verification_document,failure_code "
                "FROM engineering_database WHERE plan_id=?", (plan_id,),
            ).fetchone()
            if row is None or verification.plan_id != plan_id:
                raise KeyError("database plan is unavailable")
            verification_document = self._encode(
                verification.receipt_id, verification,
            )
            backup_id = None if backup is None else backup.backup_id
            backup_document = (
                None if backup is None else self._encode(backup.backup_id, backup)
            )
            expected = (
                backup_id, backup_document, relative,
                verification.receipt_id, verification_document, failure,
            )
            if row[4] is None:
                self._database.execute(
                    "UPDATE engineering_database SET backup_id=?,"
                    "backup_document=?,backup_relative_path=?,verification_id=?,"
                    "verification_document=?,failure_code=? WHERE plan_id=?",
                    (
                        backup_id, backup_document, relative,
                        verification.receipt_id, verification_document,
                        failure, plan_id,
                    ),
                )
            elif row[1:] != expected:
                raise RuntimeError("database result identity conflicts")

    def _encode(self, identity, value):
        if self._codec is None:
            return dumps_document(value)
        return self._codec.encode(identity, value)

    def _decode(self, identity, document, expected):
        value = (
            loads_document(document)
            if self._codec is None else self._codec.decode(identity, document)
        )
        if not isinstance(value, expected):
            raise TypeError("persisted database evidence has an unexpected contract")
        return value
