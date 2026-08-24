import hashlib
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.expert_factory import (
    DatasetPartition,
    DatasetSplitPolicy,
    HeldOutEvaluationKind,
    HeldOutVerifierKind,
    TrainingCaptureGrant,
    TrainingDataSensitivity,
    TrainingSourceKind,
    build_verified_failure_trace,
    discover_failure_clusters,
)
from fam_os.expert_factory.synthetic_generation import GeneratedExampleContent
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.factory_datasets import ProductFactoryDatasets
from fam_os.product.factory_teacher import IndependentSyntheticReviewer
from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)


NOW = datetime(2026, 7, 17, 19, tzinfo=UTC)


class FactoryDatasetProvenanceTests(unittest.TestCase):
    def test_typed_evaluation_metadata_is_encrypted_and_restart_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database, repositories, proposal = _repositories(root)
            split = DatasetSplitPolicy("factory-split-v1", "f" * 64)
            service = ProductFactoryDatasets(repositories, split, now=lambda: NOW)
            grant = _grant(proposal.proposal_id)
            service.add_grant(grant)
            source = service.capture_source(
                grant_id=grant.grant_id, source_id="typed-held-out-source",
                source_family_id=_family_for(split, DatasetPartition.HELD_OUT),
                source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
                workspace_scope="workspace:test",
                sensitivity=TrainingDataSensitivity.PRIVATE,
                license_id="owner-approved", input_text="UNSAFE_PRIVATE_PROMPT",
                reference_output="I can't help with that.",
                evaluation_kind=HeldOutEvaluationKind.SAFETY,
                evaluation_verifier=HeldOutVerifierKind.SAFE_REFUSAL,
                evaluation_requirement_id="acceptance.safety.refusal",
            )
            token = database.fetchone(
                "SELECT payload_ciphertext FROM factory_dataset_sources "
                "WHERE source_id=?", (source.source_id,),
            )[0]
            self.assertNotIn("UNSAFE_PRIVATE_PROMPT", token)
            self.assertNotIn("safe_refusal", token)
            database.close()

            database, repositories, _proposal = _repositories(root, seed=False)
            restored = repositories.dataset_staging.sources(grant.grant_id)[0]
            self.assertEqual(HeldOutEvaluationKind.SAFETY, restored.evaluation_kind)
            self.assertEqual(
                HeldOutVerifierKind.SAFE_REFUSAL, restored.evaluation_verifier,
            )
            self.assertEqual(
                "acceptance.safety.refusal",
                restored.evaluation_requirement_id,
            )
            database.close()

    def test_partial_evaluation_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories, proposal = _repositories(Path(temporary))
            split = DatasetSplitPolicy("factory-split-v1", "1" * 64)
            service = ProductFactoryDatasets(repositories, split, now=lambda: NOW)
            grant = _grant(proposal.proposal_id)
            service.add_grant(grant)
            with self.assertRaisesRegex(ValueError, "metadata must be complete"):
                service.capture_source(
                    grant_id=grant.grant_id, source_id="partial-metadata",
                    source_family_id=_family_for(split, DatasetPartition.TRAIN),
                    source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
                    workspace_scope="workspace:test",
                    sensitivity=TrainingDataSensitivity.PRIVATE,
                    license_id="owner-approved", input_text="prompt",
                    reference_output="answer",
                    evaluation_kind=HeldOutEvaluationKind.QUALITY,
                )
            database.close()

    def test_confirmed_capture_generation_review_and_restart_are_encrypted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database, repositories, proposal = _repositories(root)
            clock = [NOW]
            split = DatasetSplitPolicy("factory-split-v1", "a" * 64)
            service = ProductFactoryDatasets(repositories, split, now=lambda: clock[0])
            grant = _grant(proposal.proposal_id)
            self.assertTrue(service.add_grant(grant))
            family = _family_for(split, DatasetPartition.TRAIN)
            source = service.capture_source(
                grant_id=grant.grant_id, source_id="source-1",
                source_family_id=family,
                source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
                workspace_scope="workspace:test",
                sensitivity=TrainingDataSensitivity.PRIVATE,
                license_id="owner-approved",
                input_text="PRIVATE_TRAINING_INPUT",
                reference_output="PRIVATE_REFERENCE_OUTPUT",
            )
            clock[0] += timedelta(seconds=1)
            teacher = _Teacher()
            reviewer = IndependentSyntheticReviewer(
                lambda example: (
                    True, "python.deterministic-tests.v1",
                    "acceptance.python.tests",
                    hashlib.sha256(example.completion.encode()).hexdigest(),
                ),
                now=lambda: clock[0],
            )
            generated = service.generate(
                grant_id=grant.grant_id, source_id=source.source_id,
                teacher=teacher, reviewer=reviewer, maximum_examples=2,
            )

            self.assertEqual(2, len(generated))
            self.assertTrue(all(item[0].partition is source.partition for item in generated))
            self.assertEqual(2, len(service.accepted_examples(grant.grant_id)))
            payloads = database.fetchall(
                "SELECT payload_ciphertext FROM factory_dataset_sources "
                "UNION ALL SELECT payload_ciphertext FROM factory_synthetic_examples",
            )
            encrypted = "".join(str(row[0]) for row in payloads)
            self.assertNotIn("PRIVATE_TRAINING_INPUT", encrypted)
            self.assertNotIn("PRIVATE_REFERENCE_OUTPUT", encrypted)
            self.assertNotIn("variant input", encrypted)
            database.close()

            database, repositories, _proposal = _repositories(root, seed=False)
            restarted = ProductFactoryDatasets(repositories, split, now=lambda: clock[0])
            self.assertEqual(2, len(restarted.accepted_examples(grant.grant_id)))
            database.close()

    def test_held_out_source_is_never_disclosed_to_teacher(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories, proposal = _repositories(Path(temporary))
            split = DatasetSplitPolicy("factory-split-v1", "b" * 64)
            service = ProductFactoryDatasets(repositories, split, now=lambda: NOW)
            grant = _grant(proposal.proposal_id)
            service.add_grant(grant)
            source = service.capture_source(
                grant_id=grant.grant_id, source_id="held-out-source",
                source_family_id=_family_for(split, DatasetPartition.HELD_OUT),
                source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
                workspace_scope="workspace:test",
                sensitivity=TrainingDataSensitivity.PRIVATE,
                license_id="owner-approved", input_text="SECRET_HELD_OUT_INPUT",
                reference_output="SECRET_HELD_OUT_OUTPUT",
            )
            teacher = _Teacher()
            with self.assertRaisesRegex(PermissionError, "unavailable to teachers"):
                service.generate(
                    grant_id=grant.grant_id, source_id=source.source_id,
                    teacher=teacher, reviewer=_RejectingReviewer(), maximum_examples=1,
                )
            self.assertEqual(0, teacher.calls)
            database.close()

    def test_revocation_and_bounds_deny_before_content_is_added(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories, proposal = _repositories(Path(temporary))
            split = DatasetSplitPolicy("factory-split-v1", "c" * 64)
            service = ProductFactoryDatasets(repositories, split, now=lambda: NOW)
            grant = _grant(proposal.proposal_id, maximum_source_bytes=8)
            service.add_grant(grant)
            with self.assertRaisesRegex(PermissionError, "byte budget"):
                service.capture_source(
                    grant_id=grant.grant_id, source_id="too-large",
                    source_family_id=_family_for(split, DatasetPartition.TRAIN),
                    source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
                    workspace_scope="workspace:test",
                    sensitivity=TrainingDataSensitivity.PRIVATE,
                    license_id="owner-approved", input_text="more than eight bytes",
                    reference_output=None,
                )
            repositories.capture_grants.revoke(
                grant.grant_id, 1, "owner.revoked", NOW + timedelta(seconds=1),
            )
            with self.assertRaisesRegex(PermissionError, "revoked"):
                service.capture_source(
                    grant_id=grant.grant_id, source_id="after-revoke",
                    source_family_id=_family_for(split, DatasetPartition.TRAIN),
                    source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
                    workspace_scope="workspace:test",
                    sensitivity=TrainingDataSensitivity.PRIVATE,
                    license_id="owner-approved", input_text="x",
                    reference_output=None,
                )
            self.assertEqual((), repositories.dataset_staging.sources(grant.grant_id))
            self.assertEqual(1, len(repositories.capture_grants.revocations()))
            database.close()


class _Teacher:
    model_ref = "gemma4:26b"
    manifest_sha256 = "d" * 64

    def __init__(self):
        self.calls = 0

    def generate(self, _source, maximum_examples):
        self.calls += 1
        return tuple(
            GeneratedExampleContent(
                f"variant input {index}", f"verified completion {index}",
            )
            for index in range(maximum_examples)
        )


class _RejectingReviewer:
    def review(self, _example):
        raise AssertionError("reviewer must not receive held-out content")


def _grant(proposal_id: str, maximum_source_bytes: int = 1_000_000):
    return TrainingCaptureGrant(
        "capture-grant-1", proposal_id, "intent.code",
        (TrainingSourceKind.VERIFIED_FIXTURE,), ("workspace:test",),
        (TrainingDataSensitivity.PRIVATE,), maximum_source_bytes, 10,
        NOW, NOW + timedelta(hours=1), True,
    )


def _family_for(policy: DatasetSplitPolicy, partition: DatasetPartition) -> str:
    return next(
        f"source-family-{index}" for index in range(10_000)
        if policy.assign(f"source-family-{index}") is partition
    )


def _repositories(root: Path, *, seed: bool = True):
    database = ProductionDatabase(
        StorageSettings(root / "state/fam.sqlite3", os.geteuid()),
    )
    opened = SecureStorage(
        database, OwnerKeyStore(root / "state/master.key", os.geteuid()),
    ).open()
    repositories = CoreStorageComposition(
        database, opened.cipher, "uid:test-owner",
    ).repositories()
    proposals = repositories.factory_discovery.proposals()
    if not proposals and seed:
        traces = tuple(_trace(index) for index in (1, 2))
        for trace in traces:
            repositories.factory_discovery.add_trace(trace)
        clusters, proposals = discover_failure_clusters(traces)
        repositories.factory_discovery.add_cluster(clusters[0])
        repositories.factory_discovery.add_proposal(proposals[0])
    proposal = (proposals or repositories.factory_discovery.proposals())[0]
    return database, repositories, proposal


def _trace(index: int):
    return build_verified_failure_trace(
        verification_id=f"verification-{index}", request_id=f"request-{index}",
        candidate_id=f"candidate-{index}", capability_id="intent.code",
        failed_requirement_id="acceptance.python.tests",
        verifier_id="python.deterministic-tests.v1",
        verifier_artifact_sha256="e" * 64,
        candidate_sha256=f"{index}" * 64, model_ref="qwen3:1.7b",
        expert_tier="economical", release_id="release-1", signer_key_id="key-1",
        observed_at=NOW + timedelta(seconds=index),
    )


if __name__ == "__main__":
    unittest.main()
