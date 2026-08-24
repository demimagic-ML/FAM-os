import os
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.expert_factory import (
    AdapterTrainingMethod,
    AdapterTrainingRecipe,
    ApprovedBaseModel,
    DatasetPartition,
    DatasetSplitPolicy,
    FactoryTrainingApproval,
    TrainingCaptureGrant,
    TrainingComputeDtype,
    TrainingDataSensitivity,
    TrainingResourceBudget,
    TrainingSourceKind,
    build_captured_source,
    canonical_partition_bytes,
    build_verified_failure_trace,
    discover_failure_clusters,
    seal_factory_dataset,
)
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.factory_training_approvals import ProductFactoryTrainingApprovals
from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)
from fam_os.product.storage.factory_dataset_blob_store import FactoryDatasetBlobStore


NOW = datetime(2026, 7, 17, 20, tzinfo=UTC)
GIB = 1024**3
SPLIT = DatasetSplitPolicy("factory-split-v1", "f" * 64)


class FactoryTrainingApprovalTests(unittest.TestCase):
    def test_qlora_contract_requires_the_approved_quantization_recipe(self):
        recipe = _recipe()
        with self.assertRaisesRegex(ValueError, "4-bit NF4"):
            replace(recipe, double_quantization=False)
        with self.assertRaisesRegex(ValueError, "network denied"):
            replace(_approval("proposal-1", _Dataset()), network_allowed=True)

    def test_approval_is_encrypted_one_use_restart_safe_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database, repositories, proposal_id, dataset = _repositories(root)
            approval = _approval(proposal_id, dataset)
            self.assertTrue(repositories.training_approvals.add(approval))
            token = database.fetchone(
                "SELECT payload_ciphertext FROM factory_training_approvals "
                "WHERE approval_id=?", (approval.approval_id,),
            )[0]
            self.assertNotIn("Qwen/Qwen3-1.7B", token)
            receipt = repositories.training_approvals.consume(
                approval.approval_id, approval.one_use_job_id, 1, NOW,
            )
            self.assertEqual(approval.one_use_job_id, receipt.job_id)
            self.assertEqual(
                receipt,
                repositories.training_approvals.consume(
                    approval.approval_id, approval.one_use_job_id, 1, NOW,
                ),
            )
            with self.assertRaisesRegex(RuntimeError, "identity was reused"):
                repositories.training_approvals.consume(
                    approval.approval_id, "other-job", 1, NOW,
                )
            database.close()

            database, repositories, _, _ = _repositories(root, seed=False)
            self.assertEqual(approval, repositories.training_approvals.get(
                approval.approval_id,
            ))
            self.assertEqual(1, len(repositories.training_approvals.consumptions()))
            database.close()

    def test_expiry_and_revocation_deny_consumption_before_worker_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories, proposal_id, dataset = _repositories(Path(temporary))
            expired = replace(
                _approval(proposal_id, dataset), approval_id="approval-expired",
                one_use_job_id="job-expired", issued_at=NOW - timedelta(hours=2),
                expires_at=NOW - timedelta(hours=1),
            )
            repositories.training_approvals.add(expired)
            with self.assertRaisesRegex(PermissionError, "expired"):
                repositories.training_approvals.consume(
                    expired.approval_id, expired.one_use_job_id, 1, NOW,
                )
            approval = replace(
                _approval(proposal_id, dataset), approval_id="approval-revoked",
                one_use_job_id="job-revoked",
            )
            repositories.training_approvals.add(approval)
            revoked = repositories.training_approvals.revoke(
                approval.approval_id, 1, "owner.revoked", NOW,
            )
            self.assertEqual(2, revoked.current_revision)
            with self.assertRaisesRegex(PermissionError, "revoked"):
                repositories.training_approvals.consume(
                    approval.approval_id, approval.one_use_job_id, 1, NOW,
                )
            self.assertEqual(1, len(repositories.training_approvals.revocations()))
            database.close()

    def test_product_authority_derives_dataset_digest_and_requires_exact_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories, proposal_id, dataset = _repositories(
                Path(temporary),
            )
            service = ProductFactoryTrainingApprovals(repositories, now=lambda: NOW)
            values = _issue_values(proposal_id, dataset)
            with self.assertRaisesRegex(PermissionError, "licenses"):
                service.issue(**{
                    **values,
                    "approved_dataset_license_ids": ("wrong-license",),
                })
            approval = service.issue(**values)
            self.assertEqual(dataset.manifest_sha256, approval.sealed_dataset_sha256)
            self.assertEqual((approval,), service.approvals())
            database.close()


def _approval(proposal_id: str, dataset):
    return FactoryTrainingApproval(
        "training-approval-1", proposal_id, "intent.code",
        dataset.dataset_id, dataset.manifest_sha256,
        dataset.license_ids, dataset.sensitivities,
        ApprovedBaseModel(
            "Qwen/Qwen3-1.7B", "1" * 40, "Qwen/Qwen3-1.7B", "2" * 40,
            "Apache-2.0", "b" * 64,
        ),
        _recipe(),
        TrainingResourceBudget(
            "training-budget-1", 16, 48 * GIB, 15 * GIB, 200 * GIB,
            82, 10_000_000, "workers.full.v1",
        ),
        "c" * 64, 7_200, 10 * GIB, 2 * GIB, "training-job-1",
        NOW - timedelta(minutes=1), NOW + timedelta(hours=1), True,
    )


class _Dataset:
    dataset_id = "sealed-dataset-1"
    manifest_sha256 = "a" * 64
    license_ids = ("owner-approved",)
    sensitivities = ("private",)


def _recipe():
    return AdapterTrainingRecipe(
        "qwen3-1.7b-qlora-v1", AdapterTrainingMethod.QLORA, 16, 32, 0.05,
        ("all-linear",), 4, "nf4", True, TrainingComputeDtype.BFLOAT16,
        2_048, 3.0, 10_000, 1, 16, 2e-4, 42,
    )


def _issue_values(proposal_id: str, dataset):
    return {
        "request_id": "request-approval-1",
        "proposal_id": proposal_id,
        "sealed_dataset_id": dataset.dataset_id,
        "approved_dataset_license_ids": dataset.license_ids,
        "approved_dataset_sensitivities": dataset.sensitivities,
        "base_model": ApprovedBaseModel(
            "Qwen/Qwen3-1.7B", "1" * 40, "Qwen/Qwen3-1.7B", "2" * 40,
            "Apache-2.0", "b" * 64,
        ),
        "recipe": _recipe(),
        "resources": TrainingResourceBudget(
            "training-budget-1", 16, 48 * GIB, 15 * GIB, 200 * GIB,
            82, 10_000_000, "workers.full.v1",
        ),
        "environment_sha256": "c" * 64,
        "maximum_wall_seconds": 7_200,
        "maximum_checkpoint_bytes": 10 * GIB,
        "maximum_output_bytes": 2 * GIB,
        "one_use_job_id": "training-job-service-1",
        "lifetime_seconds": 3_600,
        "confirmed": True,
    }


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
    datasets = repositories.sealed_datasets.datasets()
    if not datasets and seed:
        grant = TrainingCaptureGrant(
            "capture-grant-approval", proposal.proposal_id, proposal.capability_id,
            (TrainingSourceKind.VERIFIED_FIXTURE,), ("workspace:test",),
            (TrainingDataSensitivity.PRIVATE,), 1_000_000, 100,
            NOW - timedelta(hours=1), NOW + timedelta(hours=1), True,
        )
        repositories.capture_grants.add(grant)
        sources = tuple(
            build_captured_source(
                source_id=f"source-{partition.value}", grant_id=grant.grant_id,
                proposal_id=proposal.proposal_id,
                source_family_id=_family(partition), split_policy=SPLIT,
                source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
                workspace_scope="workspace:test",
                sensitivity=TrainingDataSensitivity.PRIVATE,
                license_id="owner-approved", input_text=f"input {partition.value}",
                reference_output=f"output {partition.value}", captured_at=NOW,
            )
            for partition in DatasetPartition
        )
        dataset, report = seal_factory_dataset(
            dataset_id="sealed-dataset-1", proposal_id=proposal.proposal_id,
            capability_id=proposal.capability_id, sources=sources,
            examples=(), reviews=(), sealed_at=NOW,
        )
        assert dataset is not None
        assert opened.cipher is not None
        blob_store = FactoryDatasetBlobStore(
            root / "factory/datasets", opened.cipher,
            "uid:test-owner", os.geteuid(),
        )
        blobs = tuple(
            blob_store.put(
                blob_id=partition.blob_id, dataset_id=dataset.dataset_id,
                partition=partition.partition,
                plaintext_sha256=partition.ordered_records_sha256,
                payload=canonical_partition_bytes(partition, sources, (), ()),
                created_at=NOW,
            )
            for partition in dataset.partitions
        )
        repositories.sealed_datasets.record(report, dataset, blobs)
        datasets = (dataset,)
    return database, repositories, proposal.proposal_id, datasets[0]


def _family(partition: DatasetPartition) -> str:
    return next(
        f"approval-{partition.value}-family-{index}" for index in range(100_000)
        if SPLIT.assign(f"approval-{partition.value}-family-{index}") is partition
    )


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
