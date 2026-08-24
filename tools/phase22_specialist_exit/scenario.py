"""Orchestrate one governed real specialist checkpoint end to end."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

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
from fam_os.product.storage.factory_dataset_blob_store import (
    FactoryDatasetBlobStore,
)
from tools.phase22_specialist_exit.dataset import prepare_specialist_dataset
from tools.phase22_specialist_exit.evaluation import run_specialist_evaluation
from tools.phase22_specialist_exit.evidence import build_specialist_evidence
from tools.phase22_specialist_exit.settings import SpecialistExitPaths
from tools.phase22_specialist_exit.suite import seal_evaluation_suite
from tools.phase22_specialist_exit.training import run_specialist_training
from tools.phase22_specialist_exit.sample_plans import QUALITY256
from tools.phase22_specialist_exit.private_output import write_private_json_new


def run_specialist_checkpoint(
    paths: SpecialistExitPaths, run_id: str,
    sample_plan_id: str = QUALITY256.plan_id,
) -> dict[str, object]:
    paths.output_root.mkdir(mode=0o700)
    os.chmod(paths.output_root, 0o700)
    suite = seal_evaluation_suite(paths.output_root / "sealed-evaluation")
    now = datetime.now(UTC)
    state = paths.output_root / "state"
    database = ProductionDatabase(
        StorageSettings(state / "fam.sqlite3", os.geteuid()),
    )
    opened = SecureStorage(
        database, OwnerKeyStore(state / "master.key", os.geteuid()),
    ).open()
    if opened.recovery_required or opened.cipher is None:
        raise RuntimeError(f"specialist checkpoint storage failed: {opened.reason}")
    owner_id = local_owner_id(os.geteuid())
    repositories = CoreStorageComposition(
        database, opened.cipher, owner_id,
    ).repositories()
    blob_store = FactoryDatasetBlobStore(
        paths.output_root / "datasets", opened.cipher, owner_id, os.geteuid(),
    )
    try:
        prepared = prepare_specialist_dataset(
            repositories=repositories, blob_store=blob_store,
            verifier_script=(
                paths.evaluation_worker.parent / "evaluation_python_verifier.py"
            ),
            now=now, run_id=run_id, sample_plan_id=sample_plan_id,
        )
        training = run_specialist_training(
            paths=paths, repositories=repositories, blob_store=blob_store,
            prepared=prepared, now=now, run_id=run_id,
        )
        evaluation = run_specialist_evaluation(
            paths=paths, repositories=repositories, blob_store=blob_store,
            training=training, suite=suite, now=datetime.now(UTC), run_id=run_id,
        )
        evidence = build_specialist_evidence(
            run_id=run_id, suite=suite, prepared=prepared,
            training=training, evaluation=evaluation,
        )
    finally:
        database.close()
    evidence["database_sha256"] = _file_sha256(state / "fam.sqlite3")
    write_private_json_new(paths.output_root / "evidence.json", evidence)
    return evidence


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
