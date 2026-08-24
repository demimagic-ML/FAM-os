"""Composition boundary for the optional real specialist evaluator."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.training import NvidiaQloraEnvironmentProbe, NvidiaSpecialistEvaluator
from fam_os.fabric import PersistentDeviceCredentials
from fam_os.product.factory_evaluation_workspace import FactoryEvaluationWorkspace
from fam_os.product.candidate_scheduler_compatibility import (
    CandidateSchedulerCompatibilityProbe,
)


@dataclass(frozen=True, slots=True)
class FactoryEvaluationRuntimeSettings:
    environment_directory: Path
    wheelhouse_manifest: Path
    model_directory: Path
    worker_script: Path
    evaluation_workspace_root: Path
    training_workspace_root: Path
    suite_path: Path

    def __post_init__(self) -> None:
        if any(not item.is_absolute() for item in (
            self.environment_directory, self.wheelhouse_manifest,
            self.model_directory, self.worker_script,
            self.evaluation_workspace_root, self.training_workspace_root,
            self.suite_path,
        )):
            raise ValueError("factory evaluation paths must be absolute")


def compose_factory_evaluation(
    settings: FactoryEvaluationRuntimeSettings, repositories, blob_store,
    credentials: PersistentDeviceCredentials, owner_uid: int,
) -> NvidiaSpecialistEvaluator:
    python = settings.environment_directory / "bin/python"
    _directory(settings.environment_directory, "evaluation environment")
    if not python.resolve(strict=True).is_file() or not os.access(python, os.X_OK):
        raise ValueError("evaluation Python is unavailable")
    _file(settings.wheelhouse_manifest, "wheelhouse manifest")
    _directory(settings.model_directory, "evaluation base model")
    _file(settings.worker_script, "evaluation worker")
    _file(
        settings.worker_script.with_name("evaluation_python_verifier.py"),
        "evaluation Python verifier",
    )
    _directory(settings.training_workspace_root, "training workspace")
    _file(settings.suite_path, "evaluation suite")
    _workspace(settings.evaluation_workspace_root, owner_uid)
    probe = NvidiaQloraEnvironmentProbe(
        python, settings.wheelhouse_manifest, settings.worker_script,
    )
    return NvidiaSpecialistEvaluator(
        repositories=repositories, environment_probe=probe,
        workspace=FactoryEvaluationWorkspace(
            settings.evaluation_workspace_root, blob_store, owner_uid,
        ),
        environment_directory=settings.environment_directory,
        worker_script=settings.worker_script,
        model_directory=settings.model_directory,
        training_workspace_root=settings.training_workspace_root,
        suite_path=settings.suite_path,
        signer_key_id=credentials.identity.device_id,
        signing_key=credentials.identity_key,
        scheduler_probe=CandidateSchedulerCompatibilityProbe(),
    )


def _directory(path: Path, label: str) -> None:
    if not path.is_dir() or path.is_symlink():
        raise ValueError(f"{label} directory is unavailable or unsafe")


def _file(path: Path, label: str) -> None:
    try:
        metadata = path.stat(follow_symlinks=False)
    except FileNotFoundError as error:
        raise ValueError(f"{label} is unavailable") from error
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"{label} must be a regular file")


def _workspace(path: Path, owner_uid: int) -> None:
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    metadata = path.stat(follow_symlinks=False)
    if (
        path.is_symlink() or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != owner_uid or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise PermissionError("factory evaluation workspace root is unsafe")
