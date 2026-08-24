import tempfile
import unittest
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.sqlite import SQLiteEngineeringReviewStore
from fam_os.core.engineering import (
    EngineeringFindingDisposition,
    EngineeringFindingSeverity,
    EngineeringReviewCheckpoint,
    EngineeringReviewDiscipline,
    EngineeringReviewFinding,
    EngineeringReviewResolutionReceipt,
    EngineeringReviewSelection,
    EngineeringReviewService,
    EngineeringReviewStatus,
    EngineeringReviewWaiverDecision,
    review_waiver_consequences_digest,
)
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.keys import OwnerMasterKey
from fam_os.product.storage.owner_contract_codec import OwnerBoundContractCodec


NOW = datetime(2026, 7, 19, 22, 30, tzinfo=timezone.utc)


class EngineeringReviewServiceTests(unittest.TestCase):
    def test_blocking_findings_survive_restart_until_resolved_or_waived(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "reviews.sqlite3"
            store = SQLiteEngineeringReviewStore(path)
            service = EngineeringReviewService(store)
            service.record_selection(_selection())
            service.record(_checkpoint())
            with self.assertRaises(PermissionError):
                service.require_passage("review-1")
            service.resolve(EngineeringReviewResolutionReceipt(
                "repair-1", "task-1", "candidate-1", "a" * 64,
                "review-1", "finding-code", ("edit-1",),
                ("verification-evidence-1",), "reviewer",
                "independence-1", NOW,
            ))
            store.close()

            restarted_store = SQLiteEngineeringReviewStore(path)
            restarted = EngineeringReviewService(restarted_store)
            with self.assertRaises(PermissionError):
                restarted.require_passage("review-1")
            current = restarted_store.load("review-1")
            finding = next(item for item in current.findings if item.finding_id == "finding-security")
            final = restarted.waive(EngineeringReviewWaiverDecision(
                "owner-waiver-1", "review-1", "finding-security", "owner-1",
                "context-1", review_waiver_consequences_digest(current, finding),
                "review_waived", NOW,
            ))
            self.assertEqual(EngineeringReviewStatus.WAIVED, final.status)
            self.assertEqual(2, final.revision)
            restarted.require_passage("review-1")
            restarted_store.close()

    def test_producer_cannot_be_the_independent_reviewer(self):
        finding = _checkpoint().findings[0]
        with self.assertRaises(ValueError):
            EngineeringReviewCheckpoint(
                "review-2", "task-1", "candidate-1", "a" * 64,
                "same", "same", "independence-1",
                (EngineeringReviewDiscipline.CODE,), (finding,),
                EngineeringReviewStatus.BLOCKED, NOW,
            )

    def test_product_codec_migrates_plaintext_and_indexes_task_lookup(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "reviews.sqlite3"
            plain = SQLiteEngineeringReviewStore(path)
            plain.save(-1, _checkpoint())
            plain.close()

            encrypted = SQLiteEngineeringReviewStore(path, _owner_codec())
            self.assertEqual("review-1", encrypted.for_task("task-1")[0].checkpoint_id)
            self.assertEqual((), encrypted.for_task("task-2"))
            encrypted.save_evidence(_selection())
            self.assertEqual(
                _selection(), encrypted.load_evidence("selection-1"),
            )
            encrypted.close()
            connection = sqlite3.connect(path)
            document = connection.execute(
                "SELECT document FROM engineering_reviews WHERE checkpoint_id=?",
                ("review-1",),
            ).fetchone()[0]
            evidence_document = connection.execute(
                "SELECT document FROM engineering_review_evidence "
                "WHERE evidence_id=?", ("selection-1",),
            ).fetchone()[0]
            connection.close()
            self.assertNotIn("Unbounded command", document)
            self.assertTrue(document.startswith("fam.storage.aes256gcm/v1:"))
            self.assertTrue(evidence_document.startswith("fam.storage.aes256gcm/v1:"))


def _checkpoint():
    findings = (
        EngineeringReviewFinding(
            "finding-code", EngineeringReviewDiscipline.CODE,
            EngineeringFindingSeverity.MEDIUM, "Missing regression test",
            "src/a.py", ("evidence-code",), EngineeringFindingDisposition.OPEN,
        ),
        EngineeringReviewFinding(
            "finding-security", EngineeringReviewDiscipline.SECURITY,
            EngineeringFindingSeverity.HIGH, "Unbounded command",
            "src/run.py", ("evidence-security",), EngineeringFindingDisposition.OPEN,
        ),
    )
    return EngineeringReviewCheckpoint(
        "review-1", "task-1", "candidate-1", "a" * 64,
        "producer", "reviewer", "independence-1",
        (EngineeringReviewDiscipline.CODE, EngineeringReviewDiscipline.SECURITY),
        findings, EngineeringReviewStatus.BLOCKED, NOW,
    )


def _selection():
    checkpoint = _checkpoint()
    return EngineeringReviewSelection(
        "selection-1", checkpoint.task_id, checkpoint.candidate_id,
        checkpoint.changeset_sha256, "review-policy-1", "b" * 64,
        checkpoint.required_disciplines, NOW,
    )


def _owner_codec():
    key = bytes(range(32))
    key_id = "owner-key-" + hashlib.sha256(key).hexdigest()[:24]
    return OwnerBoundContractCodec(
        ProductPayloadCipher(OwnerMasterKey(key_id, key)), "owner-1",
        "engineering-review",
        (
            EngineeringReviewCheckpoint, EngineeringReviewResolutionReceipt,
            EngineeringReviewSelection, EngineeringReviewWaiverDecision,
        ),
    )


if __name__ == "__main__":
    unittest.main()
