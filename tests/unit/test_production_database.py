import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

from fam_os.product.storage.database import (
    Migration,
    ProductionDatabase,
    StorageSettings,
    apply_migrations,
)


EXPECTED_TABLES = {
    "schema_migrations", "sqlite_sequence", "requests", "plans", "events", "authorities",
    "decisions", "actions", "evidence_refs", "expert_state",
    "connector_state", "adaptation_metadata",
    "storage_metadata",
    "core_replay", "authority_grants", "plan_snapshots", "core_policies",
    "final_evidence",
    "global_attempt_budgets", "attempt_budget_reservations",
    "request_recovery",
    "inference_executions",
    "application_permissions",
    "application_executions",
    "application_action_states",
    "verification_declarations", "verification_runs",
    "document_index_grants", "document_index_documents", "document_index_chunks",
    "document_management_receipts",
    "terminal_results", "verified_learning_outcomes",
    "live_adaptation_snapshots", "model_prewarm_receipts",
    "adaptation_control_state", "adaptation_control_receipts",
    "adaptation_inference_observations", "adaptation_health_samples",
    "adaptation_drift_reports",
    "fabric_peer_enrollments",
    "fabric_peer_capabilities", "fabric_peer_performance",
    "fabric_peer_privacy_policies", "fabric_peer_management_receipts",
    "fabric_remote_context_disclosures",
    "factory_failure_traces", "factory_failure_clusters",
    "factory_capability_proposals",
    "factory_capture_grants", "factory_capture_revocations",
    "factory_dataset_sources", "factory_synthetic_examples",
    "factory_synthetic_reviews",
    "factory_training_approvals", "factory_training_approval_receipts",
    "factory_dataset_leakage_reports", "factory_sealed_datasets",
    "factory_sealed_dataset_blobs",
    "factory_training_environments", "factory_training_jobs",
    "factory_training_terminal_receipts",
    "factory_training_resource_snapshots",
    "factory_training_admission_decisions",
    "factory_evaluation_approvals", "factory_evaluation_runs",
    "factory_held_out_access_receipts", "factory_evaluation_measurements",
    "factory_evaluation_reports", "factory_evaluation_decisions",
    "factory_conversion_environments", "factory_conversion_approvals",
    "factory_conversion_receipts",
    "factory_specialist_release_lineages",
    "factory_specialist_package_receipts", "factory_canary_approvals",
    "factory_canary_reports", "factory_activation_decisions",
    "factory_specialist_lifecycle_requests",
    "factory_specialist_lifecycle_receipts",
    "engineering_grants", "engineering_authorization_audit",
    "integration_environments", "integration_environment_events",
    "engineering_secrets", "engineering_secret_audit",
    "integration_environment_start_intents",
}


class ProductionDatabaseTests(unittest.TestCase):
    def test_open_creates_private_wal_database_and_all_domain_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state" / "fam.sqlite3"
            database = ProductionDatabase(StorageSettings(path, os.geteuid()))
            database.open()
            tables = {
                row[0] for row in database.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table'"
                )
            }
            self.assertEqual(EXPECTED_TABLES, tables)
            self.assertEqual("wal", database.execute("PRAGMA journal_mode").fetchone()[0])
            self.assertEqual(1, database.execute("PRAGMA foreign_keys").fetchone()[0])
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
            self.assertEqual(0o700, stat.S_IMODE(path.parent.stat().st_mode))
            database.close()

    def test_transaction_rolls_back_as_one_unit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state" / "fam.sqlite3"
            database = ProductionDatabase(StorageSettings(path, os.geteuid()))
            database.open()
            with self.assertRaises(RuntimeError):
                with database.transaction() as connection:
                    connection.execute(
                        "INSERT INTO requests VALUES (?,?,?,?,?)",
                        ("request", "ciphertext", "accepted", "now", "now"),
                    )
                    raise RuntimeError("abort")
            count = database.execute("SELECT count(*) FROM requests").fetchone()[0]
            self.assertEqual(0, count)
            database.close()

    def test_reopening_is_idempotent_and_preserves_migration_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state" / "fam.sqlite3"
            initial = ProductionDatabase(StorageSettings(path, os.geteuid()))
            initial.open()
            initial.close()
            reopened = ProductionDatabase(StorageSettings(path, os.geteuid()))
            reopened.open()
            self.assertEqual(32, reopened.execute("SELECT count(*) FROM schema_migrations").fetchone()[0])
            reopened.close()

    def test_changed_or_future_migration_is_rejected(self) -> None:
        connection = sqlite3.connect(":memory:", isolation_level=None)
        original = Migration(1, "initial", "CREATE TABLE value(id INTEGER) STRICT;")
        apply_migrations(connection, (original,))
        with self.assertRaisesRegex(RuntimeError, "digest changed"):
            apply_migrations(connection, (Migration(1, "initial", "SELECT 1;"),))
        with self.assertRaisesRegex(RuntimeError, "unknown future"):
            apply_migrations(connection, ())

    def test_failed_migration_does_not_leave_partial_schema(self) -> None:
        connection = sqlite3.connect(":memory:", isolation_level=None)
        migration = Migration(
            1,
            "broken",
            "CREATE TABLE partial(id INTEGER) STRICT; INVALID SQL;",
        )
        with self.assertRaises(sqlite3.DatabaseError):
            apply_migrations(connection, (migration,))
        found = connection.execute(
            "SELECT count(*) FROM sqlite_schema WHERE name='partial'"
        ).fetchone()[0]
        self.assertEqual(0, found)

    def test_symlink_database_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_bytes(b"")
            link = root / "database"
            link.symlink_to(target)
            database = ProductionDatabase(StorageSettings(link, os.geteuid()))
            with self.assertRaisesRegex(OSError, "symlink"):
                database.open()


if __name__ == "__main__":
    unittest.main()
