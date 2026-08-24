"""Run the sealed paired base/candidate promotion evaluation."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fam_os.expert_factory import (
    ExpertComparisonDecision,
    FactoryEvaluationApproval,
    TrainingBackendEnvironment,
    build_evaluation_policy,
)
from fam_os.fabric import PersistentDeviceIdentityStore
from fam_os.product.composition.factory_evaluation import (
    FactoryEvaluationRuntimeSettings,
    compose_factory_evaluation,
)
from fam_os.product.factory_evaluations import (
    ProductFactoryEvaluationApprovals,
)
from fam_os.product.factory_training_workspace import (
    model_files_manifest_sha256,
)
from tools.phase22_specialist_exit.settings import SpecialistExitPaths
from tools.phase22_specialist_exit.suite import SealedEvaluationSuite
from tools.phase22_specialist_exit.training import CompletedSpecialistTraining


GIB = 1024**3


@dataclass(frozen=True, slots=True)
class CompletedSpecialistEvaluation:
    environment: TrainingBackendEnvironment
    approval: FactoryEvaluationApproval
    decision: ExpertComparisonDecision
    access_receipt: Any
    measurements: tuple[Any, ...]
    report: Any


def run_specialist_evaluation(
    *, paths: SpecialistExitPaths, repositories: Any, blob_store: Any,
    training: CompletedSpecialistTraining, suite: SealedEvaluationSuite,
    now: datetime, run_id: str,
) -> CompletedSpecialistEvaluation:
    credentials = PersistentDeviceIdentityStore(
        paths.output_root / "factory/evaluator-identity", os.geteuid(),
    ).resolve("FAM_OS stable topological sort evaluator")
    evaluator = compose_factory_evaluation(
        FactoryEvaluationRuntimeSettings(
            paths.training_environment, paths.training_manifest,
            paths.model_directory, paths.evaluation_worker,
            paths.output_root / "evaluation-workspaces",
            paths.output_root / "jobs", suite.path,
        ),
        repositories, blob_store, credentials, os.geteuid(),
    )
    environment = evaluator.probe()
    policy = build_evaluation_policy(
        policy_id="phase22-stable-toposort-promotion-v1",
        capability_id="intent.code",
        minimum_quality_cases=30,
        minimum_quality_ppm=800_000,
        minimum_improvement_ppm=100_000,
        confidence_z_ppm=1_960_000,
        maximum_unrelated_regression_ppm=0,
        maximum_p95_latency_microseconds=60_000_000,
        maximum_latency_regression_ppm=500_000,
        maximum_peak_ram_bytes=32 * GIB,
        maximum_peak_vram_bytes=15 * GIB,
        maximum_energy_joules=100_000,
        maximum_resource_regression_ppm=500_000,
        maximum_adapter_bytes=100_000_000,
        maximum_cold_start_microseconds=120_000_000,
        require_scheduler_compatibility=True,
    )
    approval = ProductFactoryEvaluationApprovals(
        repositories, now=lambda: now,
    ).issue(
        request_id=f"{run_id}-evaluation-approval",
        training_receipt_id=training.terminal.receipt_id,
        incumbent_expert_id="Qwen/Qwen3-1.7B",
        incumbent_artifact_sha256=model_files_manifest_sha256(
            paths.model_directory,
        ),
        suite_sha256=suite.sha256,
        evaluator_environment_sha256=environment.manifest_sha256,
        evaluator_script_sha256=_file_sha256(paths.evaluation_worker),
        policy=policy,
        one_use_evaluation_id=f"{run_id}-evaluation",
        lifetime_seconds=10_800,
        confirmed=True,
    )
    decision = evaluator.run(approval_id=approval.approval_id, confirmed=True)
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
        raise RuntimeError("specialist evaluation evidence is incomplete")
    leaked = tuple(paths.output_root.rglob("held-out.jsonl"))
    if leaked or not access.plaintext_discarded or not report.network_denied:
        raise RuntimeError("held-out evaluation isolation evidence is incomplete")
    return CompletedSpecialistEvaluation(
        environment, approval, decision, access, measurements, report,
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
