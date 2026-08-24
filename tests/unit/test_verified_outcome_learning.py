import os
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fam_os.adaptation import VerifiedLearningOutcome, context_token_bucket
from fam_os.core.contracts import (
    ResultAssurance,
    ResultStatus,
    TaskRequest,
    TaskResult,
)
from fam_os.core.lifecycle import AcceptanceEvidenceRecord, CandidateEvidenceRecord
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)
from fam_os.product.storage.terminal_redaction import TERMINAL_CONTENT_REDACTION


class VerifiedOutcomeLearningTests(unittest.TestCase):
    def test_context_length_is_reduced_to_a_bounded_power_of_two_bucket(self):
        self.assertEqual(128, context_token_bucket("short"))
        self.assertEqual(512, context_token_bucket("x" * 2048))
        self.assertEqual(32_768, context_token_bucket("x" * 131_072))

    def test_contract_rejects_unverified_or_content_retaining_records(self):
        values = _learning_values()
        with self.assertRaisesRegex(ValueError, "content-free"):
            VerifiedLearningOutcome(*values, verified=False)
        with self.assertRaisesRegex(ValueError, "content-free"):
            VerifiedLearningOutcome(*values, prompt_retained=True)
        with self.assertRaisesRegex(ValueError, "power of two"):
            VerifiedLearningOutcome(*values[:6], 300, *values[7:])

    def test_terminal_result_learning_and_redaction_commit_as_one_transaction(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories = _repositories(Path(temporary))
            request = TaskRequest(
                "atomic-1", "PHASE20_ATOMIC_RAW_PROMPT_NONCE",
                ("core.intent.code",), True,
            )
            candidate = CandidateEvidenceRecord(
                "candidate-atomic-1", request.request_id, "plan-atomic-1", "READY",
            )
            acceptance = AcceptanceEvidenceRecord(
                "acceptance-atomic-1", candidate.candidate_id,
                ("acceptance.text.exact",), True,
            )
            result = TaskResult(
                request.request_id, ResultStatus.VERIFIED, "READY", verified=True,
                plan_id="plan-atomic-1",
                evidence_ids=(candidate.candidate_id, acceptance.evidence_id),
                assurance=ResultAssurance.VERIFIED,
            )
            learning = VerifiedLearningOutcome(*_learning_values(
                acceptance.evidence_id, candidate.candidate_id,
            ))
            self.assertTrue(repositories.requests.add(request, "running"))
            self.assertTrue(repositories.final_evidence.add_candidate(candidate))
            self.assertTrue(repositories.final_evidence.add_acceptance(acceptance))
            database.execute(
                "CREATE TRIGGER reject_terminal BEFORE UPDATE OF state ON requests "
                "WHEN NEW.state='terminal' BEGIN SELECT RAISE(ABORT,'blocked'); END",
            )

            with self.assertRaises(sqlite3.IntegrityError):
                repositories.terminal_outcomes.finalize(request, result, learning)
            self.assertIsNone(repositories.terminal_outcomes.result(request.request_id))
            self.assertEqual(0, repositories.terminal_outcomes.result_count())
            self.assertEqual((), repositories.terminal_outcomes.learning_records())
            self.assertEqual(request, repositories.requests.get(request.request_id))
            self.assertEqual(
                "READY", repositories.final_evidence.candidate(candidate.candidate_id).content,
            )

            database.execute("DROP TRIGGER reject_terminal")
            self.assertTrue(
                repositories.terminal_outcomes.finalize(request, result, learning),
            )
            self.assertFalse(
                repositories.terminal_outcomes.finalize(request, result, learning),
            )
            self.assertEqual(result, repositories.terminal_outcomes.result(request.request_id))
            self.assertEqual(1, repositories.terminal_outcomes.result_count())
            self.assertEqual((learning,), repositories.terminal_outcomes.learning_records())
            self.assertEqual(
                TERMINAL_CONTENT_REDACTION,
                repositories.requests.get(request.request_id).prompt,
            )
            self.assertEqual(
                TERMINAL_CONTENT_REDACTION,
                repositories.final_evidence.candidate(candidate.candidate_id).content,
            )
            database.close()


def _learning_values(
    acceptance_id: str = "acceptance-1",
    candidate_id: str = "candidate-1",
) -> tuple[object, ...]:
    return (
        "verified-learning-1", "intent:code", "code", "code:model",
        "specialist", datetime(2026, 7, 17, tzinfo=UTC), 512, False,
        acceptance_id, candidate_id, "a" * 64,
    )


def _repositories(root: Path):
    database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
    storage = SecureStorage(
        database, OwnerKeyStore(root / "master.key", os.geteuid()),
    ).open()
    composition = CoreStorageComposition(database, storage.cipher, str(os.geteuid()))
    return database, composition.repositories()


if __name__ == "__main__":
    unittest.main()
