import os
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from fam_os.core.lifecycle import CandidateEvidenceRecord
from fam_os.core.production import ModelIntent
from fam_os.core.production.verification import VerificationDecision
from fam_os.expert_factory import (
    build_verified_failure_trace,
    discover_failure_clusters,
)
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.factory_discovery import ProductFactoryDiscovery
from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)
from fam_os.verification import (
    VerificationFact,
    VerificationRunRecord,
    VerificationStatus,
)


NOW = datetime(2026, 7, 17, 18, tzinfo=UTC)


class FactoryFailureDiscoveryContractTests(unittest.TestCase):
    def test_discovery_is_deterministic_and_never_authorizes_training(self):
        first = _trace(1)
        second = _trace(2)
        clusters, proposals = discover_failure_clusters((second, first))

        self.assertEqual(
            tuple(sorted((first.trace_id, second.trace_id))),
            clusters[0].trace_ids,
        )
        self.assertEqual(2, proposals[0].observation_count)
        self.assertFalse(first.training_authorized)
        self.assertFalse(proposals[0].training_authorized)
        self.assertEqual(
            discover_failure_clusters((first, second)),
            discover_failure_clusters((second, first)),
        )

    def test_one_failure_does_not_create_a_proposal(self):
        clusters, proposals = discover_failure_clusters((_trace(1),))
        self.assertEqual(1, len(clusters))
        self.assertEqual((), proposals)

    def test_digest_tampering_and_duplicate_trace_input_are_rejected(self):
        trace = _trace(1)
        with self.assertRaisesRegex(ValueError, "digest does not match"):
            replace(trace, candidate_sha256="f" * 64)
        with self.assertRaisesRegex(ValueError, "must be unique"):
            discover_failure_clusters((trace, trace))


class ProductFactoryFailureDiscoveryTests(unittest.TestCase):
    def test_signed_failed_runs_are_encrypted_persisted_and_proposal_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database, repositories = _repositories(root)
            service = ProductFactoryDiscovery(repositories)
            service.start()

            for index in (1, 2):
                request_id = f"request-{index}"
                candidate_id = f"candidate-{index}"
                raw_candidate = f"PRIVATE_REJECTED_CANDIDATE_{index}"
                self.assertTrue(repositories.final_evidence.add_candidate(
                    CandidateEvidenceRecord(
                        candidate_id, request_id, f"plan-{index}", raw_candidate,
                    ),
                ))
                service.verification_failed(
                    _record(request_id, candidate_id),
                    _decision(index, request_id, candidate_id),
                )

            self.assertEqual(2, len(service.traces()))
            self.assertEqual(1, len(service.proposals()))
            self.assertEqual(2, service.proposals()[0].observation_count)
            self.assertFalse(service.proposals()[0].training_authorized)
            service.verification_failed(
                _record("request-2", "candidate-2"),
                _decision(2, "request-2", "candidate-2"),
            )
            self.assertEqual(2, len(service.traces()))

            tokens = database.fetchall(
                "SELECT payload_ciphertext FROM factory_failure_traces",
            )
            joined = "".join(str(row[0]) for row in tokens)
            self.assertNotIn("PRIVATE_REJECTED_CANDIDATE", joined)
            self.assertNotIn("qwen3:1.7b", joined)
            database.close()

            database, repositories = _repositories(root)
            self.assertEqual(2, len(repositories.factory_discovery.traces()))
            self.assertEqual(1, len(repositories.factory_discovery.latest_proposals()))
            database.close()

    def test_unsigned_or_stopped_observation_is_not_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories = _repositories(Path(temporary))
            repositories.final_evidence.add_candidate(
                CandidateEvidenceRecord("candidate-1", "request-1", "plan-1", "bad"),
            )
            service = ProductFactoryDiscovery(repositories)
            service.start()
            decision = _decision(1, "request-1", "candidate-1")
            service.verification_failed(
                _record("request-1", "candidate-1"),
                replace(
                    decision,
                    run_record=replace(
                        decision.run_record,
                        effective_trust="local_unverified",
                        release_id=None,
                        signer_key_id=None,
                    ),
                ),
            )
            service.stop()
            service.verification_failed(
                _record("request-1", "candidate-1"), decision,
            )
            self.assertEqual((), repositories.factory_discovery.traces())
            database.close()


def _trace(index: int):
    return build_verified_failure_trace(
        verification_id=f"verification-{index}", request_id=f"request-{index}",
        candidate_id=f"candidate-{index}", capability_id="intent.code",
        failed_requirement_id="acceptance.python.tests",
        verifier_id="python.deterministic-tests.v1",
        verifier_artifact_sha256="a" * 64,
        candidate_sha256=f"{index}" * 64,
        model_ref="qwen3:1.7b", expert_tier="economical",
        release_id="release-1", signer_key_id="key-1",
        observed_at=NOW + timedelta(seconds=index),
    )


def _record(request_id: str, candidate_id: str):
    return SimpleNamespace(
        request_id=request_id,
        candidate_id=candidate_id,
        intent=ModelIntent.CODE,
        selection=SimpleNamespace(model_ref="qwen3:1.7b", tier="economical"),
    )


def _decision(index: int, request_id: str, candidate_id: str):
    run = VerificationRunRecord(
        f"verification-{index}", request_id, candidate_id,
        f"declaration-{index}", "python.deterministic-tests.v1",
        "acceptance.python.tests", "fam.verifier.python.tests", "1.0.0",
        "python.bubblewrap/v1", "a" * 64, VerificationStatus.FAILED,
        "PRIVATE_VERIFIER_FEEDBACK", (VerificationFact("exit_code", "1"),),
        "signed", "release-1", "key-1", NOW + timedelta(seconds=index),
    )
    return VerificationDecision(
        True, False, run.verifier_id, run.acceptance_id, run.feedback, run,
    )


def _repositories(root: Path):
    database = ProductionDatabase(
        StorageSettings(root / "state/fam.sqlite3", os.geteuid()),
    )
    opened = SecureStorage(
        database, OwnerKeyStore(root / "state/master.key", os.geteuid()),
    ).open()
    composition = CoreStorageComposition(database, opened.cipher, "uid:test-owner")
    return database, composition.repositories()


if __name__ == "__main__":
    unittest.main()
