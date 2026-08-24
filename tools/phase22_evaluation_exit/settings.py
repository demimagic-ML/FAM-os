from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EvaluationSmokePaths:
    training_artifact: Path
    environment_directory: Path
    wheelhouse_manifest: Path
    model_directory: Path
    worker_script: Path
    suite_path: Path

    def __post_init__(self) -> None:
        if any(not item.is_absolute() for item in (
            self.training_artifact, self.environment_directory,
            self.wheelhouse_manifest, self.model_directory,
            self.worker_script, self.suite_path,
        )):
            raise ValueError("evaluation smoke paths must be absolute")
        if not self.training_artifact.is_dir() or self.training_artifact.is_symlink():
            raise ValueError("physical training artifact is unavailable")
        if not self.environment_directory.is_dir():
            raise ValueError("evaluation environment is unavailable")
        if not self.model_directory.is_dir():
            raise ValueError("evaluation base model is unavailable")
        for path in (self.wheelhouse_manifest, self.worker_script, self.suite_path):
            if not path.is_file() or path.is_symlink():
                raise ValueError("evaluation input file is unavailable or unsafe")
