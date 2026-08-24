"""Transactional candidate-only SQLite engineering execution."""

from __future__ import annotations

import hashlib
import sqlite3
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.adapters.database.sqlite_digest import (
    sqlite_data_digest,
    sqlite_schema_digest,
)
from fam_os.adapters.database.sqlite_attempts import (
    claim_attempt,
    complete_attempt,
    record_backup,
)
from fam_os.adapters.database.sqlite_fixtures import load_fixtures
from fam_os.adapters.database.sqlite_storage import (
    artifact_digest,
    decrypt_snapshot,
    encrypted_snapshot,
    open_snapshot,
    restore_snapshot,
    secure_database_path,
)
from fam_os.adapters.database.sqlite_policy import (
    clear_migration_authorizer,
    install_migration_authorizer,
)
from fam_os.adapters.database.sqlite_sql import split_migration_statements
from fam_os.adapters.database.sqlite_verification import (
    verify_declared_rollback,
    verify_snapshot_restore,
)
from fam_os.adapters.filesystem.candidate_io import contained, read_regular
from fam_os.core.engineering.database import (
    DatabaseBackupReceipt,
    DatabaseChangePlan,
    DatabaseChangeStatus,
    DatabaseConsistencyMode,
    DatabaseEngine,
    DatabaseVerificationReceipt,
)
from fam_os.core.engineering.database_ports import (
    DatabaseBackupProtector,
    DatabaseExecutionControl,
    DatabaseExecutionPermit,
    PermitBoundDatabaseControl,
)

@dataclass(frozen=True, slots=True)
class SQLiteEngineeringResult:
    backup: DatabaseBackupReceipt
    verification: DatabaseVerificationReceipt
    backup_relative_path: str


class SQLiteDatabaseEngineeringAdapter:
    def __init__(
        self,
        protector: DatabaseBackupProtector,
        clock: Callable[[], datetime] | None = None,
        identifier: Callable[[], str] | None = None,
    ) -> None:
        self._protector = protector
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: str(uuid4()))

    def execute(
        self,
        plan: DatabaseChangePlan,
        candidate_root: Path,
        permit: DatabaseExecutionPermit,
        control: DatabaseExecutionControl,
    ) -> SQLiteEngineeringResult:
        self._admit(plan, candidate_root, permit, control)
        database_path = secure_database_path(candidate_root, plan.target.database_name)
        if database_path.stat().st_size > plan.execution_resource_impact.max_changed_bytes:
            raise ValueError("candidate database exceeds its admitted byte budget")
        control = PermitBoundDatabaseControl(control, permit, self._clock)
        connection = sqlite3.connect(database_path, isolation_level=None)
        backup_path: Path | None = None
        backup_plaintext: bytes | None = None
        context = f"fam-database-backup:{plan.plan_id}:{plan.target.target_id}"
        try:
            self._configure(connection)
            self._require_baseline(connection, plan)
            claim_attempt(candidate_root, plan.plan_id)
            backup, backup_path = self._backup(connection, candidate_root, plan, context)
            backup_plaintext = decrypt_snapshot(
                backup_path, self._protector, context,
                backup.artifact_sha256, backup.size_bytes,
            )
            record_backup(
                candidate_root, plan.plan_id, backup.backup_id,
                backup.artifact_sha256, backup.size_bytes,
                backup_path.relative_to(candidate_root).as_posix(),
            )
            self._apply(connection, candidate_root, plan, control)
            self._verify_postconditions(connection, plan)
            rollback_test_id = verify_declared_rollback(
                connection, plan,
                lambda path, digest: self._candidate_content(
                    candidate_root, path, digest,
                ),
                split_migration_statements,
                lambda: self._live(control), self._identifier,
            )
            restore_id = verify_snapshot_restore(
                backup_plaintext, backup_path.parent, plan, self._identifier,
            )
            receipt = self._receipt(
                connection, plan, permit, backup, restore_id, rollback_test_id,
            )
            complete_attempt(candidate_root, plan.plan_id, receipt.receipt_id)
            return SQLiteEngineeringResult(
                backup, receipt, backup_path.relative_to(candidate_root).as_posix(),
            )
        except BaseException:
            if backup_plaintext is not None:
                self._restore_after_failure(connection, backup_plaintext, database_path.parent)
            raise
        finally:
            connection.close()

    def _admit(self, plan, root, permit, control) -> None:
        now = self._clock()
        if plan.target.engine is not DatabaseEngine.SQLITE:
            raise ValueError("SQLite adapter cannot execute a remote database plan")
        if (
            permit.approved_changeset_id != plan.approved_changeset_id
            or permit.exact_host_id != plan.target.exact_host_id
            or not permit.active_at(now)
        ):
            raise PermissionError("database permit does not bind the exact approved target")
        if control.cancelled() or not control.authorization_active():
            raise PermissionError("database execution is cancelled or revoked")
        if not root.is_absolute():
            raise ValueError("database candidate root must be absolute")

    @staticmethod
    def _configure(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.enable_load_extension(False)
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("candidate database failed integrity verification")

    @staticmethod
    def _require_baseline(connection, plan) -> None:
        if (
            sqlite_schema_digest(connection) != plan.baseline_schema_sha256
            or sqlite_data_digest(connection) != plan.baseline_data_sha256
        ):
            raise RuntimeError("database baseline is stale")

    def _backup(self, connection, root, plan, context):
        backup_id = self._identifier()
        schema = sqlite_schema_digest(connection)
        data = sqlite_data_digest(connection)
        path, encrypted = encrypted_snapshot(
            connection, root, backup_id, self._protector, context,
        )
        if len(encrypted) > plan.execution_resource_impact.max_changed_bytes:
            path.unlink(missing_ok=True)
            raise ValueError("encrypted database backup exceeds its admitted byte budget")
        return DatabaseBackupReceipt(
            backup_id, plan.plan_id, plan.target.target_id,
            DatabaseConsistencyMode.ENGINE_NATIVE_ONLINE,
            artifact_digest(encrypted), len(encrypted), schema, data, True,
            self._clock(),
        ), path

    def _apply(self, connection, root, plan, control) -> None:
        install_migration_authorizer(connection)
        connection.set_progress_handler(
            lambda: int(control.cancelled() or not control.authorization_active()),
            1_000,
        )
        connection.execute("BEGIN IMMEDIATE")
        consumed = 0
        try:
            for step in plan.migration_steps:
                self._live(control)
                content = self._candidate_content(root, step.forward_path, step.forward_sha256)
                consumed += len(content)
                if consumed > plan.execution_resource_impact.max_changed_bytes:
                    raise ValueError("database inputs exceed their admitted byte budget")
                for statement in split_migration_statements(
                    content.decode("utf-8", "strict")
                ):
                    self._live(control)
                    connection.execute(statement)
                if sqlite_schema_digest(connection) != step.expected_schema_sha256:
                    raise RuntimeError(f"migration {step.step_id} schema postcondition failed")
            if plan.fixture_set is not None:
                fixture_path = contained(root, plan.fixture_set.manifest_path)
                consumed += fixture_path.stat(follow_symlinks=False).st_size
                if consumed > plan.execution_resource_impact.max_changed_bytes:
                    raise ValueError("database inputs exceed their admitted byte budget")
                load_fixtures(
                    connection, plan.fixture_set,
                    lambda path, digest: self._candidate_content(root, path, digest),
                    lambda: self._live(control),
                )
            self._live(control)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.set_progress_handler(None, 0)
            clear_migration_authorizer(connection)

    @staticmethod
    def _verify_postconditions(connection, plan) -> None:
        supported = {"schema-match", "foreign-keys", "transaction-test"}
        if set(plan.postcondition_ids) - supported:
            raise ValueError("database plan names an unsupported postcondition")
        if "foreign-keys" in plan.postcondition_ids:
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("database foreign-key postcondition failed")
        if "transaction-test" in plan.postcondition_ids:
            before = sqlite_schema_digest(connection)
            connection.execute("BEGIN")
            connection.execute("CREATE TABLE __fam_transaction_probe(value INTEGER)")
            connection.rollback()
            if sqlite_schema_digest(connection) != before:
                raise RuntimeError("database transaction rollback postcondition failed")

    def _receipt(self, connection, plan, permit, backup, restore_id, rollback_test_id):
        return DatabaseVerificationReceipt(
            self._identifier(), plan.plan_id, plan.target.target_id,
            permit.permit_id, backup.backup_id, DatabaseChangeStatus.VERIFIED,
            tuple(step.step_id for step in plan.migration_steps),
            sqlite_schema_digest(connection), sqlite_data_digest(connection),
            ("atomic-migration-rollback", rollback_test_id), restore_id,
            plan.postcondition_ids, None, self._clock(),
        )

    @staticmethod
    def _candidate_content(root, relative, expected):
        path = contained(root, relative)
        details = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
            raise PermissionError("database input must be a single-link regular file")
        content = read_regular(path, 4 * 1024 * 1024)
        if hashlib.sha256(content).hexdigest() != expected:
            raise RuntimeError("database input digest does not match its contract")
        return content

    @staticmethod
    def _live(control) -> None:
        if control.cancelled() or not control.authorization_active():
            raise PermissionError("database execution was cancelled or revoked")

    @staticmethod
    def _restore_after_failure(connection, plaintext, directory) -> None:
        snapshot, path = open_snapshot(plaintext, directory)
        try:
            restore_snapshot(snapshot, connection)
        finally:
            snapshot.close()
            path.unlink(missing_ok=True)
