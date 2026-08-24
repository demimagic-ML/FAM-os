"""Content-free evidence assembly for the physical QLoRA smoke."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path

from fam_os.expert_factory import (
    AdapterTrainingJob,
    DatasetLeakageReport,
    FactoryCapabilityProposal,
    FactoryTrainingApproval,
    SealedFactoryDataset,
    TrainingAdmissionDecision,
    TrainingBackendEnvironment,
    TrainingCaptureGrant,
    TrainingTerminalReceipt,
    TrainingTerminalStatus,
)
from tools.phase22_training_exit.settings import TrainingSmokePaths


def build_smoke_evidence(
    *, paths: TrainingSmokePaths, environment: TrainingBackendEnvironment,
    proposal: FactoryCapabilityProposal, grant: TrainingCaptureGrant,
    dataset: SealedFactoryDataset, leakage: DatasetLeakageReport,
    approval: FactoryTrainingApproval, result: TrainingTerminalReceipt,
    admissions: tuple[TrainingAdmissionDecision, ...],
    jobs: tuple[AdapterTrainingJob, ...],
    terminals: tuple[TrainingTerminalReceipt, ...],
) -> dict[str, object]:
    if not isinstance(result, TrainingTerminalReceipt):
        raise RuntimeError("physical training was not admitted")
    output = paths.output_root / "jobs" / approval.one_use_job_id / "output"
    evidence = {
        "contract_version": "fam.factory.physical-training-smoke/v1alpha1",
        "environment": _json(asdict(environment)),
        "proposal": _json(asdict(proposal)),
        "grant": _json(asdict(grant)),
        "dataset": _json(asdict(dataset)),
        "leakage_report": _json(asdict(leakage)),
        "approval": _json(asdict(approval)),
        "admissions": [_json(asdict(item)) for item in admissions],
        "jobs": [_json(asdict(item)) for item in jobs],
        "terminals": [_json(asdict(item)) for item in terminals],
        "result": _json(asdict(result)),
        "output_files": _file_inventory(output),
        "passed": result.status is TrainingTerminalStatus.COMPLETED,
    }
    if result.status is TrainingTerminalStatus.COMPLETED:
        if not (
            result.network_denied and result.held_out_absent
            and result.base_weights_frozen
            and not result.unexpected_trainable_parameters
        ):
            raise RuntimeError("completed physical training lacks safety evidence")
    return evidence


def _file_inventory(root: Path) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    if not root.is_dir() or root.is_symlink():
        return values
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError("physical training output contains a symlink")
        if path.is_file():
            values.append({
                "bytes": path.stat().st_size,
                "path": path.relative_to(root).as_posix(),
                "sha256": _file_sha256(path),
            })
    return values


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
