"""Fresh-authority reconciliation for interrupted SQLite engineering."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.adapters.database.sqlite_attempts import (
    backup_state,
    read_attempt,
    recover_attempt,
)
from fam_os.adapters.database.sqlite_digest import (
    sqlite_data_digest,
    sqlite_schema_digest,
)
from fam_os.adapters.database.sqlite_storage import (
    decrypt_snapshot,
    open_snapshot,
    restore_snapshot,
    secure_database_path,
)
from fam_os.adapters.filesystem.candidate_io import contained
from fam_os.core.engineering.database import (
    DatabaseBackupReceipt,
    DatabaseChangePlan,
    DatabaseChangeStatus,
    DatabaseEngine,
    DatabaseVerificationReceipt,
)
from fam_os.core.engineering.database_ports import (
    DatabaseBackupProtector,
    DatabaseExecutionControl,
    DatabaseExecutionPermit,
)


class SQLiteDatabaseRecoveryAdapter:
    def __init__(
        self,
        protector: DatabaseBackupProtector,
        clock: Callable[[], datetime] | None = None,
        identifier: Callable[[], str] | None = None,
    ) -> None:
        self._protector = protector
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: str(uuid4()))

    def reconcile(
        self,
        plan: DatabaseChangePlan,
        candidate_root: Path,
        permit: DatabaseExecutionPermit,
        control: DatabaseExecutionControl,
    ) -> DatabaseVerificationReceipt:
        self._admit(plan, permit, control)
        state = read_attempt(candidate_root, plan.plan_id)
        if state.startswith(("verified:", "recovered:")):
            raise PermissionError("database attempt is already terminal")
        database_path = secure_database_path(candidate_root, plan.target.database_name)
        connection = sqlite3.connect(database_path, isolation_level=None)
        try:
            backup_id = None
            if not self._at_baseline(connection, plan):
                backup_id = self._restore_recorded_backup(
                    connection, candidate_root, plan, state,
                )
            if not self._at_baseline(connection, plan):
                raise RuntimeError("database restart reconciliation requires recovery")
            receipt_id = self._identifier()
            rollback_id = self._identifier()
            recover_attempt(candidate_root, plan.plan_id, receipt_id)
            return DatabaseVerificationReceipt(
                receipt_id, plan.plan_id, plan.target.target_id,
                permit.permit_id, backup_id,
                DatabaseChangeStatus.ROLLED_BACK, (),
                plan.baseline_schema_sha256, plan.baseline_data_sha256,
                ("restart-reconciliation",), self._identifier(),
                plan.postcondition_ids, rollback_id, self._clock(),
            )
        finally:
            connection.close()

    def rollback_verified(
        self,
        plan: DatabaseChangePlan,
        prior: DatabaseVerificationReceipt,
        backup: DatabaseBackupReceipt,
        backup_relative_path: str,
        candidate_root: Path,
        permit: DatabaseExecutionPermit,
        control: DatabaseExecutionControl,
    ) -> DatabaseVerificationReceipt:
        self._admit(plan, permit, control)
        state = read_attempt(candidate_root, plan.plan_id)
        if state != f"verified:{prior.receipt_id}":
            raise PermissionError("database rollback does not match the terminal attempt")
        if (
            prior.status is not DatabaseChangeStatus.VERIFIED
            or prior.plan_id != plan.plan_id
            or prior.target_id != plan.target.target_id
            or prior.backup_id != backup.backup_id
            or prior.execution_permit_id == permit.permit_id
            or backup.plan_id != plan.plan_id
            or backup.target_id != plan.target.target_id
        ):
            raise PermissionError("database rollback evidence identities do not match")
        artifact = contained(candidate_root, backup_relative_path)
        context = f"fam-database-backup:{plan.plan_id}:{plan.target.target_id}"
        plaintext = decrypt_snapshot(
            artifact, self._protector, context,
            backup.artifact_sha256, backup.size_bytes,
        )
        database_path = secure_database_path(candidate_root, plan.target.database_name)
        connection = sqlite3.connect(database_path, isolation_level=None)
        try:
            snapshot, path = open_snapshot(plaintext, artifact.parent)
            try:
                restore_snapshot(snapshot, connection)
            finally:
                snapshot.close()
                path.unlink(missing_ok=True)
            if not self._at_baseline(connection, plan):
                raise RuntimeError("explicit database rollback missed its baseline")
            return self._rolled_back_receipt(
                plan, backup.backup_id, prior.applied_step_ids,
                "explicit-backup-rollback", candidate_root, permit.permit_id,
            )
        finally:
            connection.close()

    def _restore_recorded_backup(self, connection, root, plan, state) -> str:
        record = backup_state(state)
        if record is None:
            raise RuntimeError("database attempt has no recoverable backup stage")
        backup_id, sha256, size, relative = record
        artifact = contained(root, relative)
        context = f"fam-database-backup:{plan.plan_id}:{plan.target.target_id}"
        plaintext = decrypt_snapshot(
            artifact, self._protector, context, sha256, size,
        )
        snapshot, path = open_snapshot(plaintext, artifact.parent)
        try:
            restore_snapshot(snapshot, connection)
        finally:
            snapshot.close()
            path.unlink(missing_ok=True)
        return backup_id

    def _rolled_back_receipt(
        self, plan, backup_id, applied, test_id, root, permit_id,
    ):
        receipt_id = self._identifier()
        receipt = DatabaseVerificationReceipt(
            receipt_id, plan.plan_id, plan.target.target_id, permit_id, backup_id,
            DatabaseChangeStatus.ROLLED_BACK, applied,
            plan.baseline_schema_sha256, plan.baseline_data_sha256,
            (test_id,), self._identifier(), plan.postcondition_ids,
            self._identifier(), self._clock(),
        )
        recover_attempt(root, plan.plan_id, receipt_id)
        return receipt

    def _admit(self, plan, permit, control) -> None:
        if plan.target.engine is not DatabaseEngine.SQLITE:
            raise ValueError("SQLite recovery cannot reconcile a remote database")
        if (
            permit.approved_changeset_id != plan.approved_changeset_id
            or permit.exact_host_id != plan.target.exact_host_id
            or not permit.active_at(self._clock())
            or control.cancelled()
            or not control.authorization_active()
        ):
            raise PermissionError("database recovery lacks fresh exact authority")

    @staticmethod
    def _at_baseline(connection, plan) -> bool:
        return (
            sqlite_schema_digest(connection) == plan.baseline_schema_sha256
            and sqlite_data_digest(connection) == plan.baseline_data_sha256
        )
