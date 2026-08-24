"""Run one owner-approved, isolated, one-step QLoRA job through product services."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fam_os.expert_factory import (
    AdapterTrainingMethod,
    AdapterTrainingRecipe,
    ApprovedBaseModel,
    DatasetPartition,
    DatasetSplitPolicy,
    FactoryCapabilityProposal,
    TrainingCaptureGrant,
    TrainingComputeDtype,
    TrainingDataSensitivity,
    TrainingResourceBudget,
    TrainingSourceKind,
    TrainingTerminalReceipt,
    build_verified_failure_trace,
    discover_failure_clusters,
)
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.composition.factory_training import (
    FactoryTrainingRuntimeSettings,
    compose_factory_training,
)
from fam_os.product.factory_datasets import ProductFactoryDatasets
from fam_os.product.factory_training_approvals import ProductFactoryTrainingApprovals
from fam_os.product.owner_identity import local_owner_id
from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)
from fam_os.product.storage.factory_dataset_blob_store import FactoryDatasetBlobStore
from tools.phase22_training_exit.settings import TrainingSmokePaths
from tools.phase22_training_exit.validation import build_smoke_evidence


GIB = 1024**3
_SPLIT = DatasetSplitPolicy(
    "phase22-physical-smoke-split-v1",
    hashlib.sha256(b"fam-os-phase22-physical-smoke-split-v1").hexdigest(),
)


def run_training_smoke(paths: TrainingSmokePaths) -> dict[str, object]:
    paths.output_root.mkdir(mode=0o700)
    os.chmod(paths.output_root, 0o700)
    now = datetime.now(UTC)
    state = paths.output_root / "state"
    database = ProductionDatabase(
        StorageSettings(state / "fam.sqlite3", os.geteuid()),
    )
    opened = SecureStorage(
        database, OwnerKeyStore(state / "master.key", os.geteuid()),
    ).open()
    if opened.recovery_required or opened.cipher is None:
        raise RuntimeError(f"training smoke storage failed: {opened.reason}")
    owner_id = local_owner_id(os.geteuid())
    repositories = CoreStorageComposition(
        database, opened.cipher, owner_id,
    ).repositories()
    blob_store = FactoryDatasetBlobStore(
        paths.output_root / "datasets", opened.cipher, owner_id, os.geteuid(),
    )
    datasets = ProductFactoryDatasets(
        repositories, _SPLIT, blob_store, now=lambda: now,
    )
    try:
        proposal = _seed_proposal(repositories, now)
        grant = _grant(proposal.proposal_id, proposal.capability_id, now)
        if not datasets.add_grant(grant):
            raise RuntimeError("physical smoke capture grant was not new")
        _capture_partitions(datasets, grant.grant_id)
        dataset, leakage = datasets.seal(
            dataset_id="phase22-physical-smoke-dataset",
            grant_id=grant.grant_id,
        )
        if dataset is None or not leakage.passed:
            raise RuntimeError("physical smoke dataset did not pass leakage gates")
        training = compose_factory_training(
            FactoryTrainingRuntimeSettings(
                paths.environment_directory, paths.wheelhouse_manifest,
                paths.model_directory, paths.worker_script,
                paths.output_root / "jobs",
            ),
            repositories, blob_store, os.geteuid(),
        )
        environment = training.probe_environment()
        approval = ProductFactoryTrainingApprovals(
            repositories, now=lambda: now,
        ).issue(
            request_id="phase22-physical-smoke",
            proposal_id=proposal.proposal_id,
            sealed_dataset_id=dataset.dataset_id,
            approved_dataset_license_ids=dataset.license_ids,
            approved_dataset_sensitivities=dataset.sensitivities,
            base_model=ApprovedBaseModel(
                "Qwen/Qwen3-1.7B",
                "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
                "Qwen/Qwen3-1.7B",
                "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
                "Apache-2.0",
                "1579816840e7f7a694ef449c4d3d3d9a6e83001452e69a38b225df67e5851b7e",
            ),
            recipe=_recipe(), resources=_resources(),
            environment_sha256=environment.manifest_sha256,
            maximum_wall_seconds=900,
            maximum_checkpoint_bytes=GIB,
            maximum_output_bytes=2 * GIB,
            one_use_job_id="phase22-physical-smoke-job",
            lifetime_seconds=3_600, confirmed=True,
        )
        result = training.start(
            request_id="phase22-physical-smoke-start",
            approval_id=approval.approval_id, confirmed=True,
        )
        if not isinstance(result, TrainingTerminalReceipt):
            raise RuntimeError(
                "physical training admission was denied: "
                + ",".join(result.reason_codes),
            )
        evidence = build_smoke_evidence(
            paths=paths, environment=environment, proposal=proposal,
            grant=grant, dataset=dataset, leakage=leakage,
            approval=approval, result=result,
            admissions=training.admissions(), jobs=training.jobs(),
            terminals=training.terminals(),
        )
    finally:
        database.close()
    evidence["database_sha256"] = _file_sha256(state / "fam.sqlite3")
    return evidence


def _seed_proposal(
    repositories: Any, now: datetime,
) -> FactoryCapabilityProposal:
    traces = tuple(
        build_verified_failure_trace(
            verification_id=f"phase22-smoke-verification-{index}",
            request_id=f"phase22-smoke-request-{index}",
            candidate_id=f"phase22-smoke-candidate-{index}",
            capability_id="intent.code",
            failed_requirement_id="acceptance.python.tests",
            verifier_id="python.deterministic-tests.v1",
            verifier_artifact_sha256="a" * 64,
            candidate_sha256=f"{index}" * 64,
            model_ref="qwen2.5-coder:7b", expert_tier="specialist",
            release_id="phase22-source-release", signer_key_id="phase22-source-key",
            observed_at=now + timedelta(microseconds=index),
        )
        for index in (1, 2)
    )
    for trace in traces:
        repositories.factory_discovery.add_trace(trace)
    clusters, proposals = discover_failure_clusters(traces)
    if len(clusters) != 1 or len(proposals) != 1:
        raise RuntimeError("physical smoke failure discovery was not deterministic")
    repositories.factory_discovery.add_cluster(clusters[0])
    repositories.factory_discovery.add_proposal(proposals[0])
    return proposals[0]


def _grant(
    proposal_id: str, capability_id: str, now: datetime,
) -> TrainingCaptureGrant:
    return TrainingCaptureGrant(
        "phase22-physical-smoke-grant", proposal_id, capability_id,
        (TrainingSourceKind.VERIFIED_FIXTURE,), ("workspace:phase22-smoke",),
        (TrainingDataSensitivity.PRIVATE,), 4 * 1024**2, 32,
        now, now + timedelta(hours=1), True,
    )


def _capture_partitions(datasets: ProductFactoryDatasets, grant_id: str) -> None:
    records = {
        DatasetPartition.TRAIN: (
            "Write a Python function add(a, b).",
            "def add(a, b):\n    return a + b",
        ),
        DatasetPartition.VALIDATION: (
            "Write a Python function multiply(a, b).",
            "def multiply(a, b):\n    return a * b",
        ),
        DatasetPartition.HELD_OUT: (
            "Write a Python function subtract(a, b).",
            "def subtract(a, b):\n    return a - b",
        ),
    }
    for partition, (prompt, completion) in records.items():
        source_id = f"phase22-smoke-{partition.value}"
        datasets.capture_source(
            grant_id=grant_id, source_id=source_id,
            source_family_id=_family(partition),
            source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
            workspace_scope="workspace:phase22-smoke",
            sensitivity=TrainingDataSensitivity.PRIVATE,
            license_id="owner-authored-smoke-fixture",
            input_text=prompt, reference_output=completion,
        )


def _family(partition: DatasetPartition) -> str:
    return next(
        f"phase22-smoke-{partition.value}-family-{index}"
        for index in range(100_000)
        if _SPLIT.assign(f"phase22-smoke-{partition.value}-family-{index}") is partition
    )


def _recipe() -> AdapterTrainingRecipe:
    return AdapterTrainingRecipe(
        "qwen3-1.7b-qlora-physical-smoke-v1", AdapterTrainingMethod.QLORA,
        8, 16, 0.05, ("all-linear",), 4, "nf4", True,
        TrainingComputeDtype.BFLOAT16, 256, 1.0, 1, 1, 1, 2e-4, 42,
    )


def _resources() -> TrainingResourceBudget:
    return TrainingResourceBudget(
        "phase22-physical-smoke-budget", 12, 24 * GIB, 10 * GIB,
        10 * GIB, 80, 500_000, "factory.training.physical-smoke.v1",
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
