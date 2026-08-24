"""Validated inputs for a real promotion-eligible Phase 22 checkpoint."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SpecialistExitPaths:
    output_root: Path
    training_environment: Path
    training_manifest: Path
    model_directory: Path
    training_worker: Path
    evaluation_worker: Path
    recover_existing_output: bool = False

    def __post_init__(self) -> None:
        values = (
            self.output_root, self.training_environment, self.training_manifest,
            self.model_directory, self.training_worker, self.evaluation_worker,
        )
        if any(not item.is_absolute() for item in values):
            raise ValueError("specialist exit paths must be absolute")
        if self.recover_existing_output:
            if self.output_root.is_symlink() or not self.output_root.is_dir():
                raise ValueError("specialist recovery output root is unavailable or unsafe")
        elif self.output_root.exists() or self.output_root.is_symlink():
            raise FileExistsError("specialist exit output root already exists")
        if not self.training_environment.is_dir():
            raise ValueError("training environment is unavailable")
        if not self.model_directory.is_dir() or self.model_directory.is_symlink():
            raise ValueError("base model directory is unavailable or unsafe")
        for item in (
            self.training_manifest, self.training_worker, self.evaluation_worker,
        ):
            if not item.is_file() or item.is_symlink():
                raise ValueError("specialist exit input file is unavailable or unsafe")
