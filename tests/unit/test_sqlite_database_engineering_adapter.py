import hashlib
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.database import (
    SQLiteDatabaseEngineeringAdapter,
    SQLiteDatabaseRecoveryAdapter,
    sqlite_data_digest,
    sqlite_schema_digest,
)
from fam_os.adapters.database.sqlite_attempts import claim_attempt, record_backup
from fam_os.adapters.database.sqlite_storage import encrypted_snapshot
from fam_os.core.engineering import (
    DatabaseChangePlan,
    DatabaseEngine,
    DatabaseEnvironment,
    DatabaseExecutionPermit,
    DatabaseFixtureSet,
    DatabaseMigrationStep,
    DatabaseTarget,
    EngineeringAuthority,
    EngineeringResourceImpact,
)


NOW = datetime(2026, 7, 19, 18, 0, tzinfo=timezone.utc)


class ReversingProtector:
    def encrypt(self, plaintext: bytes, context: str) -> bytes:
        return b"protected:" + context.encode("ascii") + b":" + plaintext[::-1]

    def decrypt(self, ciphertext: bytes, context: str) -> bytes:
        prefix = b"protected:" + context.encode("ascii") + b":"
        if not ciphertext.startswith(prefix):
            raise ValueError("backup authentication failed")
        return ciphertext[len(prefix):][::-1]


class LiveControl:
    def __init__(self, cancel_after: int | None = None, active: bool = True) -> None:
        self.cancel_after = cancel_after
        self.active = active
        self.checks = 0

    def cancelled(self) -> bool:
        self.checks += 1
        return self.cancel_after is not None and self.checks >= self.cancel_after

    def authorization_active(self) -> bool:
        return self.active


class SQLiteDatabaseEngineeringAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.database = self.root / "app.db"
        connection = sqlite3.connect(self.database)
        connection.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL) STRICT")
        connection.commit()
        self.baseline_schema = sqlite_schema_digest(connection)
        self.baseline_data = sqlite_data_digest(connection)
        connection.close()
        self.sql = "CREATE TABLE notes(id INTEGER PRIMARY KEY, body TEXT NOT NULL) STRICT;"
        self.forward = self._write("db/001.sql", self.sql.encode())
        self.rollback = self._write("db/001_down.sql", b"DROP TABLE notes;")
        fixture = {"tables": [{"name": "notes", "columns": ["id", "body"], "rows": [[1, "hello"]]}]}
        self.fixture = self._write(
            "db/fixtures.json",
            json.dumps(fixture, separators=(",", ":")).encode(),
        )
        expected = sqlite3.connect(":memory:")
        expected.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL) STRICT")
        expected.execute(self.sql)
        self.expected_schema = sqlite_schema_digest(expected)
        expected.close()
        target = DatabaseTarget(
            "db-1", DatabaseEngine.SQLITE, DatabaseEnvironment.CANDIDATE,
            "app.db", None, "host-1", False,
        )
        step = DatabaseMigrationStep(
            "step-1", 1, "db/001.sql", self.forward,
            "db/001_down.sql", self.rollback, False, True,
            self.expected_schema,
        )
        fixtures = DatabaseFixtureSet(
            "fixture-1", "db/fixtures.json", self.fixture, 1, True, False,
        )
        self.plan = DatabaseChangePlan(
            "plan-1", "task-1", "candidate-1", target,
            self.baseline_schema, self.baseline_data, (step,), fixtures,
            True, True, ("schema-match", "foreign-keys", "transaction-test"),
            (EngineeringAuthority.EXECUTE, EngineeringAuthority.MODIFY),
            EngineeringResourceImpact(300, 1, 0, 4, 16_777_216, 0),
            "changeset-1", NOW,
        )
        self.permit = DatabaseExecutionPermit(
            "permit-1", "changeset-1", "host-1", NOW, NOW + timedelta(hours=1),
        )
        identifiers = iter(f"id-{index}" for index in range(20))
        self.protector = ReversingProtector()
        self.adapter = SQLiteDatabaseEngineeringAdapter(
            self.protector, lambda: NOW + timedelta(minutes=1),
            lambda: next(identifiers),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_applies_fixture_and_proves_encrypted_backup_restore(self) -> None:
        result = self.adapter.execute(self.plan, self.root, self.permit, LiveControl())
        connection = sqlite3.connect(self.database)
        self.assertEqual(connection.execute("SELECT * FROM notes").fetchall(), [(1, "hello")])
        connection.close()
        backup = self.root / result.backup_relative_path
        self.assertTrue(backup.read_bytes().startswith(b"protected:"))
        self.assertEqual(result.verification.schema_sha256, self.expected_schema)
        self.assertEqual(result.verification.applied_step_ids, ("step-1",))

    def test_wrong_approval_has_no_effect(self) -> None:
        permit = replace(self.permit, approved_changeset_id="another-changeset")
        with self.assertRaisesRegex(PermissionError, "exact approved"):
            self.adapter.execute(self.plan, self.root, permit, LiveControl())
        self.assertFalse((self.root / ".fam").exists())
        self.assertEqual(self._tables(), ["users"])

    def test_stale_baseline_has_no_effect(self) -> None:
        connection = sqlite3.connect(self.database)
        connection.execute("INSERT INTO users VALUES (1, 'changed')")
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(RuntimeError, "baseline is stale"):
            self.adapter.execute(self.plan, self.root, self.permit, LiveControl())
        self.assertFalse((self.root / ".fam").exists())
        self.assertEqual(self._tables(), ["users"])

    def test_cancellation_rolls_back_partial_migration(self) -> None:
        with self.assertRaisesRegex(PermissionError, "cancelled"):
            self.adapter.execute(self.plan, self.root, self.permit, LiveControl(cancel_after=4))
        self.assertEqual(self._tables(), ["users"])

    def test_revocation_before_execution_has_no_effect(self) -> None:
        with self.assertRaisesRegex(PermissionError, "cancelled or revoked"):
            self.adapter.execute(self.plan, self.root, self.permit, LiveControl(active=False))
        self.assertFalse((self.root / ".fam").exists())

    def test_tampered_migration_is_rejected_and_baseline_restored(self) -> None:
        (self.root / "db" / "001.sql").write_text("DROP TABLE users;", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "digest"):
            self.adapter.execute(self.plan, self.root, self.permit, LiveControl())
        self.assertEqual(self._tables(), ["users"])

    def test_tampered_rollback_is_rejected_and_live_database_is_restored(self) -> None:
        path = self.root / "db" / "001_down.sql"
        content = b"DELETE FROM notes;"
        path.write_bytes(content)
        rollback_digest = hashlib.sha256(content).hexdigest()
        step = replace(self.plan.migration_steps[0], rollback_sha256=rollback_digest)
        plan = replace(self.plan, migration_steps=(step,))
        with self.assertRaisesRegex(RuntimeError, "rollback does not restore"):
            self.adapter.execute(plan, self.root, self.permit, LiveControl())
        self.assertEqual(self._tables(), ["users"])

    def test_host_database_attach_from_untrusted_sql_is_denied(self) -> None:
        outside = self.root.parent / f"outside-{self.root.name}.db"
        sql = f"ATTACH DATABASE '{outside}' AS escaped;"
        path = self.root / "db" / "001.sql"
        content = sql.encode()
        path.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        step = replace(
            self.plan.migration_steps[0], forward_sha256=digest,
            expected_schema_sha256=self.baseline_schema,
        )
        plan = replace(self.plan, migration_steps=(step,), fixture_set=None)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                self.adapter.execute(plan, self.root, self.permit, LiveControl())
            self.assertFalse(outside.exists())
            self.assertEqual(self._tables(), ["users"])
        finally:
            outside.unlink(missing_ok=True)

    def test_completed_plan_cannot_be_replayed_after_database_reset(self) -> None:
        self.adapter.execute(self.plan, self.root, self.permit, LiveControl())
        self.database.unlink()
        connection = sqlite3.connect(self.database)
        connection.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL) STRICT")
        connection.commit()
        connection.close()
        with self.assertRaises(FileExistsError):
            self.adapter.execute(self.plan, self.root, self.permit, LiveControl())
        self.assertEqual(self._tables(), ["users"])

    def test_restart_reconciliation_restores_recorded_snapshot(self) -> None:
        claim_attempt(self.root, self.plan.plan_id)
        connection = sqlite3.connect(self.database, isolation_level=None)
        context = f"fam-database-backup:{self.plan.plan_id}:{self.plan.target.target_id}"
        path, _encrypted = encrypted_snapshot(
            connection, self.root, "crash-backup", self.protector, context,
        )
        record_backup(
            self.root, self.plan.plan_id, "crash-backup",
            hashlib.sha256(_encrypted).hexdigest(), len(_encrypted),
            path.relative_to(self.root).as_posix(),
        )
        connection.execute(self.sql)
        connection.execute("INSERT INTO notes VALUES (1, 'unverified')")
        connection.close()
        identifiers = iter(("reconcile-receipt", "rollback-receipt", "restore-test"))
        recovery = SQLiteDatabaseRecoveryAdapter(
            self.protector, lambda: NOW + timedelta(minutes=2),
            lambda: next(identifiers),
        )
        receipt = recovery.reconcile(
            self.plan, self.root, self.permit, LiveControl(),
        )
        self.assertEqual(receipt.status.value, "rolled_back")
        self.assertEqual(receipt.backup_id, "crash-backup")
        self.assertEqual(self._tables(), ["users"])

    def test_verified_change_can_be_explicitly_rolled_back(self) -> None:
        result = self.adapter.execute(self.plan, self.root, self.permit, LiveControl())
        identifiers = iter(("rollback-receipt", "restore-test", "rollback-evidence"))
        rollback = SQLiteDatabaseRecoveryAdapter(
            self.protector, lambda: NOW + timedelta(minutes=2),
            lambda: next(identifiers),
        )
        with self.assertRaisesRegex(PermissionError, "identities do not match"):
            rollback.rollback_verified(
                self.plan, result.verification, result.backup,
                result.backup_relative_path, self.root,
                self.permit, LiveControl(),
            )
        receipt = rollback.rollback_verified(
            self.plan, result.verification, result.backup,
            result.backup_relative_path, self.root,
            replace(self.permit, permit_id="rollback-permit"), LiveControl(),
        )
        self.assertEqual(receipt.status.value, "rolled_back")
        self.assertEqual(self._tables(), ["users"])

    def test_tampered_backup_cannot_drive_explicit_rollback(self) -> None:
        result = self.adapter.execute(self.plan, self.root, self.permit, LiveControl())
        artifact = self.root / result.backup_relative_path
        artifact.write_bytes(artifact.read_bytes() + b"tampered")
        rollback = SQLiteDatabaseRecoveryAdapter(
            self.protector, lambda: NOW + timedelta(minutes=2), lambda: "rollback-id",
        )
        with self.assertRaisesRegex(RuntimeError, "size does not match"):
            rollback.rollback_verified(
                self.plan, result.verification, result.backup,
                result.backup_relative_path, self.root,
                replace(self.permit, permit_id="rollback-permit"), LiveControl(),
            )
        self.assertEqual(self._tables(), ["notes", "users"])

    def test_restart_reconciliation_of_started_baseline_needs_no_backup(self) -> None:
        claim_attempt(self.root, self.plan.plan_id)
        identifiers = iter(("reconcile-receipt", "rollback-receipt", "restore-test"))
        recovery = SQLiteDatabaseRecoveryAdapter(
            self.protector, lambda: NOW + timedelta(minutes=2),
            lambda: next(identifiers),
        )
        receipt = recovery.reconcile(
            self.plan, self.root, self.permit, LiveControl(),
        )
        self.assertIsNone(receipt.backup_id)
        with self.assertRaisesRegex(PermissionError, "already terminal"):
            recovery.reconcile(self.plan, self.root, self.permit, LiveControl())

    def test_symlink_and_hardlink_database_targets_are_rejected(self) -> None:
        real = self.root / "real.db"
        self.database.rename(real)
        self.database.symlink_to(real)
        with self.assertRaises((PermissionError, OSError)):
            self.adapter.execute(self.plan, self.root, self.permit, LiveControl())
        self.database.unlink()
        self.database.hardlink_to(real)
        with self.assertRaisesRegex(PermissionError, "single-link"):
            self.adapter.execute(self.plan, self.root, self.permit, LiveControl())

    def _write(self, relative: str, content: bytes) -> str:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return hashlib.sha256(content).hexdigest()

    def _tables(self) -> list[str]:
        connection = sqlite3.connect(self.database)
        try:
            return [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
            )]
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
