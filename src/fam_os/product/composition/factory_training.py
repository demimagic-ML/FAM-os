"""Composition boundary for the optional real NVIDIA Expert Factory backend."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.training import NvidiaQloraBackend, NvidiaQloraEnvironmentProbe
from fam_os.adapters.training.resource_observer import LinuxTrainingResourceObserver
from fam_os.product.factory_training import ProductFactoryTraining
from fam_os.product.factory_training_workspace import FactoryTrainingWorkspace


@dataclass(frozen=True, slots=True)
class FactoryTrainingRuntimeSettings:
    environment_directory: Path
    wheelhouse_manifest: Path
    model_directory: Path
    worker_script: Path
    workspace_root: Path

    def __post_init__(self) -> None:
        values = (
            self.environment_directory, self.wheelhouse_manifest,
            self.model_directory, self.worker_script, self.workspace_root,
        )
        if any(not value.is_absolute() for value in values):
            raise ValueError("factory training paths must be absolute")


def compose_factory_training(
    settings: FactoryTrainingRuntimeSettings,
    repositories,
    blob_store,
    owner_uid: int,
) -> ProductFactoryTraining:
    python = settings.environment_directory / "bin/python"
    _require_directory(settings.environment_directory, "training environment")
    _require_python(python)
    _require_regular_file(settings.wheelhouse_manifest, "wheelhouse manifest")
    _require_directory(settings.model_directory, "base model")
    _require_regular_file(settings.worker_script, "training worker")
    _prepare_workspace_root(settings.workspace_root, owner_uid)
    probe = NvidiaQloraEnvironmentProbe(
        python, settings.wheelhouse_manifest, settings.worker_script,
    )
    workspace = FactoryTrainingWorkspace(
        settings.workspace_root, blob_store, owner_uid,
    )
    backend = NvidiaQloraBackend(
        repositories=repositories, environment_probe=probe,
        workspace=workspace,
        environment_directory=settings.environment_directory,
        worker_script=settings.worker_script,
        model_directory=settings.model_directory,
    )
    return ProductFactoryTraining(
        repositories, backend,
        LinuxTrainingResourceObserver(settings.workspace_root),
    )


def _require_directory(path: Path, label: str) -> None:
    if not path.is_dir() or path.is_symlink():
        raise ValueError(f"{label} directory is unavailable or unsafe")


def _require_regular_file(path: Path, label: str) -> None:
    try:
        metadata = path.stat(follow_symlinks=False)
    except FileNotFoundError as error:
        raise ValueError(f"{label} is unavailable") from error
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"{label} must be a regular file")


def _require_python(path: Path) -> None:
    try:
        target = path.resolve(strict=True)
        metadata = target.stat(follow_symlinks=False)
    except FileNotFoundError as error:
        raise ValueError("training Python is unavailable") from error
    if not stat.S_ISREG(metadata.st_mode) or not os.access(target, os.X_OK):
        raise ValueError("training Python must resolve to an executable file")


def _prepare_workspace_root(path: Path, owner_uid: int) -> None:
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    metadata = path.stat(follow_symlinks=False)
    if (
        path.is_symlink() or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != owner_uid or metadata.st_mode & 0o077
    ):
        raise PermissionError("factory training workspace root is unsafe")
