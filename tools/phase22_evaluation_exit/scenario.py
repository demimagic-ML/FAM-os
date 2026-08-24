from __future__ import annotations

import hashlib
import os
from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from fam_os.expert_factory import TrainingTerminalStatus, build_evaluation_policy
from fam_os.fabric import PersistentDeviceIdentityStore
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.composition.factory_evaluation import (
    FactoryEvaluationRuntimeSettings,
    compose_factory_evaluation,
)
from fam_os.product.factory_evaluations import ProductFactoryEvaluationApprovals
from fam_os.product.owner_identity import local_owner_id
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.factory_dataset_blob_store import FactoryDatasetBlobStore
from fam_os.product.factory_training_workspace import model_files_manifest_sha256
from tools.phase22_evaluation_exit.settings import EvaluationSmokePaths


GIB = 1024**3


def run_evaluation_smoke(
    paths: EvaluationSmokePaths,
    run_id: str = "phase22-physical-evaluation",
) -> dict[str, object]:
    state = paths.training_artifact / "state"
    database = ProductionDatabase(
        StorageSettings(state / "fam.sqlite3", os.geteuid()),
    )
    opened = SecureStorage(
        database, OwnerKeyStore(state / "master.key", os.geteuid()),
    ).open()
    if opened.recovery_required or opened.cipher is None:
        raise RuntimeError(f"evaluation smoke storage failed: {opened.reason}")
    owner_id = local_owner_id(os.geteuid())
    repositories = CoreStorageComposition(
        database, opened.cipher, owner_id,
    ).repositories()
    blob_store = FactoryDatasetBlobStore(
        paths.training_artifact / "datasets", opened.cipher,
        owner_id, os.geteuid(),
    )
    credentials = PersistentDeviceIdentityStore(
        paths.training_artifact / "factory/evaluator-identity", os.geteuid(),
    ).resolve("FAM_OS factory evaluator")
    evaluator = compose_factory_evaluation(
        FactoryEvaluationRuntimeSettings(
            paths.environment_directory, paths.wheelhouse_manifest,
            paths.model_directory, paths.worker_script,
            paths.training_artifact / "evaluation-workspaces",
            paths.training_artifact / "jobs", paths.suite_path,
        ),
        repositories, blob_store, credentials, os.geteuid(),
    )
    try:
        terminal = next(
            item for item in repositories.training_jobs.terminals()
            if item.status is TrainingTerminalStatus.COMPLETED
        )
        environment = evaluator.probe()
        policy = build_evaluation_policy(
            policy_id="phase22-code-specialist-evaluation-v1",
            capability_id="intent.code", minimum_quality_cases=30,
            minimum_quality_ppm=800_000, minimum_improvement_ppm=100_000,
            confidence_z_ppm=1_960_000,
            maximum_unrelated_regression_ppm=0,
            maximum_p95_latency_microseconds=60_000_000,
            maximum_latency_regression_ppm=500_000,
            maximum_peak_ram_bytes=24 * GIB,
            maximum_peak_vram_bytes=15 * GIB,
            maximum_energy_joules=100_000,
            maximum_resource_regression_ppm=500_000,
            maximum_adapter_bytes=100_000_000,
            maximum_cold_start_microseconds=120_000_000,
            require_scheduler_compatibility=True,
        )
        approval = ProductFactoryEvaluationApprovals(
            repositories, now=lambda: datetime.now(UTC),
        ).issue(
            request_id=run_id,
            training_receipt_id=terminal.receipt_id,
            incumbent_expert_id="Qwen/Qwen3-1.7B",
            incumbent_artifact_sha256=model_files_manifest_sha256(
                paths.model_directory,
            ),
            suite_sha256=_file_sha256(paths.suite_path),
            evaluator_environment_sha256=environment.manifest_sha256,
            evaluator_script_sha256=_file_sha256(paths.worker_script),
            policy=policy,
            one_use_evaluation_id=run_id,
            lifetime_seconds=3600, confirmed=True,
        )
        decision = evaluator.run(
            approval_id=approval.approval_id, confirmed=True,
        )
        access = repositories.factory_evaluations.access_receipt(
            approval.one_use_evaluation_id,
        )
        report = repositories.factory_evaluations.report(
            approval.one_use_evaluation_id,
        )
        measurements = repositories.factory_evaluations.measurements(
            approval.one_use_evaluation_id,
        )
        if access is None or report is None or not measurements:
            raise RuntimeError("physical evaluator did not commit complete evidence")
        leaked = tuple(
            str(item.relative_to(paths.training_artifact))
            for item in paths.training_artifact.rglob("held-out.jsonl")
        )
        evidence = {
            "contract_version": "fam.factory.physical-evaluation-smoke/v1alpha1",
            "environment": _json(asdict(environment)),
            "approval": _json(asdict(approval)),
            "held_out_access": _json(asdict(access)),
            "measurements": [_json(asdict(item)) for item in measurements],
            "report": _json(asdict(report)),
            "decision": _json(asdict(decision)),
            "held_out_plaintext_paths_after_run": leaked,
            "passed": (
                not decision.promotable
                and "quality.sample_count_insufficient" in decision.reason_codes
                and report.network_denied and access.plaintext_discarded
                and not leaked
            ),
        }
    finally:
        database.close()
    return evidence


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return value
