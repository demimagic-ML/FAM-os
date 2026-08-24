"""Durability and encryption tests for specialist rollback and retirement."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from fam_os.expert_factory import (
    FactorySpecialistLifecycleAction,
    build_specialist_lifecycle_receipt,
    build_specialist_lifecycle_request,
)
from tests.unit.test_factory_evaluation import NOW
from tests.unit.test_factory_training_approval import _repositories


class FactorySpecialistLifecycleRepositoryTests(unittest.TestCase):
    def test_pending_request_restarts_and_completion_retains_encrypted_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database, repositories, _, _ = _repositories(root)
            request = build_specialist_lifecycle_request(
                request_id="factory-lifecycle-owner-request-1",
                action=FactorySpecialistLifecycleAction.RETIRE,
                release_id="release-specialist-1",
                target_release_id=None,
                expected_lifecycle_revision=3,
                reason_code="owner-retired-private-sentinel",
                regression_evidence_sha256=None,
                remove_artifact=True,
                issued_at=NOW,
            )
            self.assertTrue(repositories.factory_lifecycle.begin(request))
            self.assertEqual((request,), repositories.factory_lifecycle.pending())
            database.close()

            database, repositories, _, _ = _repositories(root, seed=False)
            self.assertEqual((request,), repositories.factory_lifecycle.pending())
            receipt = build_specialist_lifecycle_receipt(
                receipt_id="factory-lifecycle-receipt-1",
                request_id=request.request_id,
                request_sha256=request.request_sha256,
                action=request.action,
                release_id=request.release_id,
                target_release_id=None,
                reason_code=request.reason_code,
                lifecycle_revision=5,
                active_release_id=None,
                runtime_model_removed=True,
                artifact_removed=True,
                audit_retained=True,
                completed_at=NOW,
            )
            repositories.factory_lifecycle.complete(receipt)
            self.assertEqual((), repositories.factory_lifecycle.pending())
            self.assertEqual((receipt,), repositories.factory_lifecycle.receipts())
            database.close()

            raw = sqlite3.connect(root / "state/fam.sqlite3")
            payloads = raw.execute(
                "SELECT payload_ciphertext FROM "
                "factory_specialist_lifecycle_requests UNION ALL SELECT "
                "payload_ciphertext FROM factory_specialist_lifecycle_receipts",
            ).fetchall()
            raw.close()
            self.assertNotIn(
                b"owner-retired-private-sentinel",
                "".join(row[0] for row in payloads).encode(),
            )

    def test_forced_rollback_requires_regression_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "regression evidence"):
            build_specialist_lifecycle_request(
                request_id="factory-forced-rollback-1",
                action=FactorySpecialistLifecycleAction.FORCED_REGRESSION_ROLLBACK,
                release_id="release-specialist-2",
                target_release_id="release-specialist-1",
                expected_lifecycle_revision=4,
                reason_code="production-regression",
                regression_evidence_sha256=None,
                remove_artifact=False,
                issued_at=NOW,
            )


if __name__ == "__main__":
    unittest.main()
