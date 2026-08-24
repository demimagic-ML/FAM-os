import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fam_os.core.engineering import CandidateWorkspace, IntegrationEnvironmentStatus
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.integration_environment_repository import (
    SqliteIntegrationEnvironmentRepository,
)
from tests.contract.schema_integration_environment_fixtures import (
    NOW,
    integration_environment_schema_values,
)


class IntegrationEnvironmentRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        storage = SecureStorage(
            ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid())),
            OwnerKeyStore(root / "master.key", os.geteuid()),
        ).open()
        assert storage.database is not None and storage.cipher is not None
        self.database = storage.database
        self.cipher = storage.cipher
        self.repository = SqliteIntegrationEnvironmentRepository(
            storage.database, storage.cipher, "owner-1",
        )
        _service, self.plan, _permit, self.receipt, self.result = (
            integration_environment_schema_values()
        )
        self.candidate = CandidateWorkspace(
            self.plan.candidate_id, self.plan.task_id, "baseline-1",
            "/owner/workspace", self.plan.candidate_root, NOW,
            "copy", "a" * 64, (),
        )

    def tearDown(self):
        self.database.close()
        self.temporary.cleanup()

    def test_start_is_encrypted_restart_safe_and_replay_safe(self):
        self.repository.begin_start(self.plan, self.candidate)
        self.repository.record_permit(self.result.permit)
        self.repository.put_started(self.plan, self.candidate, self.result)
        stored = self.repository.get(self.plan.environment_id)
        self.assertEqual(self.plan, stored.plan)
        self.assertEqual(self.candidate, stored.candidate)
        self.assertEqual(self.result, stored.start_result)
        self.assertEqual((stored,), self.repository.active())
        row = self.database.fetchone(
            "SELECT plan_ciphertext FROM integration_environments WHERE environment_id=?",
            (self.plan.environment_id,),
        )
        self.assertNotIn(self.plan.task_id, row[0])
        restarted = SqliteIntegrationEnvironmentRepository(
            self.database, self.cipher, "owner-1",
        )
        self.assertEqual(self.result, restarted.get(self.plan.environment_id).start_result)
        self.assertEqual(
            (stored,), restarted.for_task(self.plan.task_id),
        )
        self.assertEqual("committed", restarted.intent(self.plan.environment_id).state)
        with self.assertRaises(Exception):
            self.repository.put_started(self.plan, self.candidate, self.result)

    def test_cleanup_is_append_only_and_terminal(self):
        self.repository.put_started(self.plan, self.candidate, self.result)
        cleaned = replace(
            self.receipt, receipt_id="cleanup-1",
            status=IntegrationEnvironmentStatus.CLEANED,
            cleanup_evidence_ids=("removed-container:container-1",),
        )
        self.repository.record_cleanup(
            self.plan.environment_id, cleaned, reconciled=True,
        )
        stored = self.repository.get(self.plan.environment_id)
        self.assertEqual("cleaned", stored.state)
        self.assertEqual(cleaned, stored.latest_receipt)
        self.assertEqual((self.receipt, cleaned), self.repository.receipts(self.plan.environment_id))
        self.assertEqual((), self.repository.active())
        with self.assertRaises(PermissionError):
            self.repository.record_cleanup(
                self.plan.environment_id, replace(cleaned, receipt_id="cleanup-2"),
                reconciled=False,
            )

    def test_interrupted_permit_is_encrypted_pending_and_recoverable(self):
        self.repository.begin_start(self.plan, self.candidate)
        self.repository.record_permit(self.result.permit)
        self.assertEqual(
            "recovery_required",
            self.repository.record_interrupted(self.plan.environment_id),
        )
        pending = self.repository.pending_intents()
        self.assertEqual(self.result.permit, pending[0].permit)
        cleaned = replace(
            self.receipt, receipt_id="interrupted-cleanup",
            status=IntegrationEnvironmentStatus.CLEANED,
            cleanup_evidence_ids=("recovery-probed:test",),
        )
        self.repository.record_intent_recovery(self.plan.environment_id, cleaned)
        intent = self.repository.intent(self.plan.environment_id)
        self.assertEqual("recovered", intent.state)
        self.assertEqual(cleaned, intent.recovery_receipt)
        self.assertEqual((), self.repository.pending_intents())

    def test_prepermit_intent_closes_without_runtime_recovery(self):
        self.repository.begin_start(self.plan, self.candidate)
        self.repository.record_prelaunch_failed(self.plan.environment_id)
        self.assertEqual(
            "prelaunch_failed", self.repository.intent(self.plan.environment_id).state,
        )

    def test_mismatched_plan_digest_is_rejected_before_write(self):
        with self.assertRaisesRegex(ValueError, "identities"):
            self.repository.put_started(
                replace(self.plan, task_id="other"), self.candidate, self.result,
            )
        self.assertIsNone(self.repository.get(self.plan.environment_id))


if __name__ == "__main__":
    unittest.main()
