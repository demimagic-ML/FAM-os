import os
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.expert_factory import (
    DatasetLeakageKind,
    DatasetPartition,
    DatasetSplitPolicy,
    HeldOutEvaluationKind,
    HeldOutVerifierKind,
    TrainingCaptureGrant,
    TrainingDataSensitivity,
    TrainingSourceKind,
    build_captured_source,
    canonical_partition_bytes,
    build_verified_failure_trace,
    discover_failure_clusters,
    seal_factory_dataset,
)
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.factory_datasets import ProductFactoryDatasets
from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)
from fam_os.product.storage.factory_dataset_blob_store import FactoryDatasetBlobStore


NOW = datetime(2026, 7, 17, 21, tzinfo=UTC)
SPLIT = DatasetSplitPolicy("factory-split-v1", "a" * 64)


class FactoryDatasetSealingTests(unittest.TestCase):
    def test_typed_evaluation_metadata_is_bound_into_partition_bytes(self):
        sources = (
            _source(DatasetPartition.TRAIN, "source-train", "p1", "a1"),
            _source(DatasetPartition.VALIDATION, "source-validation", "p2", "a2"),
            build_captured_source(
                source_id="source-held-out", grant_id="capture-grant-1",
                proposal_id="proposal-1",
                source_family_id=_family(
                    DatasetPartition.HELD_OUT, "source-held-out",
                ),
                split_policy=SPLIT,
                source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
                workspace_scope="workspace:test",
                sensitivity=TrainingDataSensitivity.PRIVATE,
                license_id="owner-approved", input_text="unsafe prompt",
                reference_output="I can't help with that.", captured_at=NOW,
                evaluation_kind=HeldOutEvaluationKind.SAFETY,
                evaluation_verifier=HeldOutVerifierKind.SAFE_REFUSAL,
                evaluation_requirement_id="acceptance.safety.refusal",
            ),
        )
        dataset, report = seal_factory_dataset(
            dataset_id="typed-evaluation-dataset", proposal_id="proposal-1",
            capability_id="intent.code", sources=sources, examples=(), reviews=(),
            sealed_at=NOW,
        )
        self.assertTrue(report.passed)
        assert dataset is not None
        held_out = next(
            item for item in dataset.partitions
            if item.partition is DatasetPartition.HELD_OUT
        )
        document = json.loads(
            canonical_partition_bytes(held_out, sources, (), ()).decode(),
        )
        self.assertEqual("safety", document["evaluation_kind"])
        self.assertEqual("safe_refusal", document["evaluation_verifier"])
        self.assertEqual(
            "acceptance.safety.refusal", document["evaluation_requirement_id"],
        )

    def test_exact_and_near_cross_partition_leakage_block_sealing(self):
        train = _source(
            DatasetPartition.TRAIN, "source-train", "same prompt", "same answer",
        )
        validation = _source(
            DatasetPartition.VALIDATION, "source-validation",
            "validation prompt", "validation answer",
        )
        held_out = _source(
            DatasetPartition.HELD_OUT, "source-held-out", "same prompt", "same answer",
        )
        dataset, report = seal_factory_dataset(
            dataset_id="leaking-dataset", proposal_id="proposal-1",
            capability_id="intent.code", sources=(train, validation, held_out),
            examples=(), reviews=(), sealed_at=NOW,
        )

        self.assertIsNone(dataset)
        self.assertFalse(report.passed)
        self.assertEqual(
            {DatasetLeakageKind.EXACT_CROSS_PARTITION},
            {item.kind for item in report.findings},
        )

    def test_same_partition_duplicates_are_removed_before_immutable_seal(self):
        sources = (
            _source(DatasetPartition.TRAIN, "source-train-a", "p1", "a1"),
            _source(DatasetPartition.TRAIN, "source-train-b", "p1", "a1"),
            _source(DatasetPartition.VALIDATION, "source-validation", "p2", "a2"),
            _source(DatasetPartition.HELD_OUT, "source-held-out", "p3", "a3"),
        )
        dataset, report = seal_factory_dataset(
            dataset_id="deduplicated-dataset", proposal_id="proposal-1",
            capability_id="intent.code", sources=sources, examples=(), reviews=(),
            sealed_at=NOW,
        )

        self.assertIsNotNone(dataset)
        assert dataset is not None
        self.assertTrue(report.passed)
        self.assertEqual(("source-train-b",), report.exact_duplicates_removed)
        self.assertEqual(3, sum(item.record_count for item in dataset.partitions))
        self.assertNotIn("source-train-b", dataset.source_ids)

    def test_product_seal_is_encrypted_idempotent_and_restart_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database, repositories, proposal_id, cipher = _repositories(root)
            blob_store = FactoryDatasetBlobStore(
                root / "factory/datasets", cipher,
                "uid:test-owner", os.geteuid(),
            )
            service = ProductFactoryDatasets(
                repositories, SPLIT,
                blob_store,
                now=lambda: NOW,
            )
            grant = _grant(proposal_id)
            service.add_grant(grant)
            for partition, source_id in (
                (DatasetPartition.TRAIN, "source-train"),
                (DatasetPartition.VALIDATION, "source-validation"),
                (DatasetPartition.HELD_OUT, "source-held-out"),
            ):
                service.capture_source(
                    grant_id=grant.grant_id, source_id=source_id,
                    source_family_id=_family(partition, source_id),
                    source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
                    workspace_scope="workspace:test",
                    sensitivity=TrainingDataSensitivity.PRIVATE,
                    license_id="owner-approved",
                    input_text=f"PRIVATE_{partition.value}_INPUT",
                    reference_output=f"PRIVATE_{partition.value}_OUTPUT",
                )
            dataset, report = service.seal(
                dataset_id="sealed-dataset-1", grant_id=grant.grant_id,
            )
            self.assertIsNotNone(dataset)
            assert dataset is not None
            self.assertTrue(report.passed)
            self.assertEqual((dataset, report), service.seal(
                dataset_id=dataset.dataset_id, grant_id=grant.grant_id,
            ))
            token = database.fetchone(
                "SELECT payload_ciphertext FROM factory_sealed_datasets "
                "WHERE dataset_id=?", (dataset.dataset_id,),
            )[0]
            self.assertNotIn(SPLIT.policy_id, token)
            blobs = repositories.sealed_datasets.blobs(dataset.dataset_id)
            self.assertEqual(tuple(DatasetPartition), tuple(
                item.partition for item in blobs
            ))
            for blob in blobs:
                payload = blob_store.read(blob)
                self.assertIn(f"PRIVATE_{blob.partition.value}_INPUT", payload.decode())
                if blob.partition is not DatasetPartition.HELD_OUT:
                    self.assertNotIn("PRIVATE_held_out_INPUT", payload.decode())
            database.close()

            database, repositories, _, _ = _repositories(root, seed=False)
            self.assertEqual(dataset, repositories.sealed_datasets.get(dataset.dataset_id))
            self.assertEqual(report, repositories.sealed_datasets.report(report.report_id))
            self.assertEqual(blobs, repositories.sealed_datasets.blobs(dataset.dataset_id))
            database.close()


def _source(
    partition: DatasetPartition, source_id: str, input_text: str, output: str,
):
    return build_captured_source(
        source_id=source_id, grant_id="capture-grant-1",
        proposal_id="proposal-1", source_family_id=_family(partition, source_id),
        split_policy=SPLIT, source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
        workspace_scope="workspace:test",
        sensitivity=TrainingDataSensitivity.PRIVATE,
        license_id="owner-approved", input_text=input_text,
        reference_output=output, captured_at=NOW,
    )


def _family(partition: DatasetPartition, prefix: str) -> str:
    return next(
        f"{prefix}-family-{index}" for index in range(100_000)
        if SPLIT.assign(f"{prefix}-family-{index}") is partition
    )


def _grant(proposal_id: str) -> TrainingCaptureGrant:
    return TrainingCaptureGrant(
        "capture-grant-1", proposal_id, "intent.code",
        (TrainingSourceKind.VERIFIED_FIXTURE,), ("workspace:test",),
        (TrainingDataSensitivity.PRIVATE,), 1_000_000, 100,
        NOW - timedelta(minutes=1), NOW + timedelta(hours=1), True,
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
    return database, repositories, (
        proposals or repositories.factory_discovery.proposals()
    )[0].proposal_id, opened.cipher


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
