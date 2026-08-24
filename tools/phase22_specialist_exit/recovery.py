"""Recover content-free checkpoint evidence from committed durable receipts."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from fam_os.product.composition.core_storage import (
    CoreStorageComposition,
)
from fam_os.product.owner_identity import local_owner_id
from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)
from tools.phase22_specialist_exit.dataset import (
    PreparedSpecialistDataset,
    verify_specialist_fixtures,
)
from tools.phase22_specialist_exit.evaluation import CompletedSpecialistEvaluation
from tools.phase22_specialist_exit.evidence import build_specialist_evidence
from tools.phase22_specialist_exit.settings import SpecialistExitPaths
from tools.phase22_specialist_exit.suite import load_sealed_evaluation_suite
from tools.phase22_specialist_exit.training import CompletedSpecialistTraining
from tools.phase22_specialist_exit.sample_plans import QUALITY256
from tools.phase22_specialist_exit.private_output import write_private_json_new


def recover_specialist_checkpoint_evidence(
    paths: SpecialistExitPaths, run_id: str,
    sample_plan_id: str = QUALITY256.plan_id,
) -> dict[str, object]:
    """Project evidence without repeating training or held-out evaluation."""
    if not paths.recover_existing_output:
        raise ValueError("specialist evidence recovery was not explicitly requested")
    evidence_path = paths.output_root / "evidence.json"
    if evidence_path.exists() or evidence_path.is_symlink():
        raise FileExistsError("specialist checkpoint evidence already exists")
    suite = load_sealed_evaluation_suite(
        paths.output_root / "sealed-evaluation",
    )
    state = paths.output_root / "state"
    database_path = state / "fam.sqlite3"
    database = ProductionDatabase(
        StorageSettings(database_path, os.geteuid()),
    )
    opened = SecureStorage(
        database, OwnerKeyStore(state / "master.key", os.geteuid()),
    ).open()
    if opened.recovery_required or opened.cipher is None:
        raise RuntimeError(f"specialist recovery storage failed: {opened.reason}")
    repositories = CoreStorageComposition(
        database, opened.cipher, local_owner_id(os.geteuid()),
    ).repositories()
    try:
        dataset = _required(
            repositories.sealed_datasets.get(f"{run_id}-dataset"), "dataset",
        )
        proposal = _one(
            tuple(
                item for item in repositories.factory_discovery.proposals()
                if item.proposal_id == dataset.proposal_id
            ),
            "capability proposal",
        )
        grant = _required(
            repositories.capture_grants.get(dataset.grant_id), "capture grant",
        )
        leakage = _required(
            repositories.sealed_datasets.report(dataset.leakage_report_id),
            "dataset leakage report",
        )
        prepared = PreparedSpecialistDataset(
            sample_plan_id, proposal, grant, dataset, leakage,
            verify_specialist_fixtures(
                paths.evaluation_worker.parent / "evaluation_python_verifier.py",
                sample_plan_id,
            ),
        )
        job_id = f"{run_id}-job"
        terminal = _required(
            repositories.training_jobs.terminal(job_id), "training terminal receipt",
        )
        training = CompletedSpecialistTraining(
            _required(
                repositories.training_jobs.environment(terminal.environment_sha256),
                "training environment",
            ),
            _required(
                repositories.training_approvals.get(terminal.approval_id),
                "training approval",
            ),
            terminal,
            repositories.training_admissions.decisions(),
            repositories.training_jobs.jobs(),
            repositories.training_jobs.terminals(),
        )
        evaluation_id = f"{run_id}-evaluation"
        evaluation_approval = _one(
            tuple(
                item for item in repositories.factory_evaluations.approvals()
                if item.one_use_evaluation_id == evaluation_id
            ),
            "evaluation approval",
        )
        evaluation = CompletedSpecialistEvaluation(
            _required(
                repositories.training_jobs.environment(
                    evaluation_approval.evaluator_environment_sha256,
                ),
                "evaluation environment",
            ),
            evaluation_approval,
            _required(
                repositories.factory_evaluations.decision(evaluation_id),
                "evaluation decision",
            ),
            _required(
                repositories.factory_evaluations.access_receipt(evaluation_id),
                "held-out access receipt",
            ),
            repositories.factory_evaluations.measurements(evaluation_id),
            _required(
                repositories.factory_evaluations.report(evaluation_id),
                "evaluation report",
            ),
        )
        if not evaluation.measurements:
            raise RuntimeError("specialist recovery has no evaluation measurements")
        evidence = build_specialist_evidence(
            run_id=run_id, suite=suite, prepared=prepared,
            training=training, evaluation=evaluation,
        )
    finally:
        database.close()
    evidence["database_sha256"] = _file_sha256(database_path)
    write_private_json_new(evidence_path, evidence)
    return evidence


def _required(value: Any, name: str) -> Any:
    if value is None:
        raise RuntimeError(f"specialist recovery is missing {name}")
    return value


def _one(values: tuple[Any, ...], name: str) -> Any:
    if len(values) != 1:
        raise RuntimeError(f"specialist recovery requires exactly one {name}")
    return values[0]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
