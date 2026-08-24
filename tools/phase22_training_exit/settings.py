"""Validated filesystem inputs for one physical QLoRA smoke run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TrainingSmokePaths:
    output_root: Path
    environment_directory: Path
    wheelhouse_manifest: Path
    model_directory: Path
    worker_script: Path

    def __post_init__(self) -> None:
        if any(not path.is_absolute() for path in (
            self.output_root, self.environment_directory,
            self.wheelhouse_manifest, self.model_directory,
            self.worker_script,
        )):
            raise ValueError("training smoke paths must be absolute")
        if self.output_root.exists() or self.output_root.is_symlink():
            raise FileExistsError("training smoke output root already exists")
        if not self.environment_directory.is_dir():
            raise ValueError("training environment directory is unavailable")
        if not self.wheelhouse_manifest.is_file():
            raise ValueError("training wheelhouse manifest is unavailable")
        if not self.model_directory.is_dir():
            raise ValueError("training model directory is unavailable")
        if not self.worker_script.is_file() or self.worker_script.is_symlink():
            raise ValueError("training worker script is unavailable or unsafe")
