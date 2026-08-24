"""Validated paths for one physical specialist release qualification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SpecialistReleaseExitPaths:
    training_artifact: Path
    conversion_environment: Path
    conversion_manifest: Path
    llama_cpp: Path
    model_directory: Path
    prompt_configuration: Path
    verifier_tests: Path
    ollama: Path

    def __post_init__(self) -> None:
        if any(not path.is_absolute() for path in self._paths()):
            raise ValueError("specialist release paths must be absolute")
        for path in (
            self.training_artifact,
            self.conversion_environment,
            self.llama_cpp,
            self.model_directory,
        ):
            if not path.is_dir() or path.is_symlink():
                raise ValueError("specialist release directory is unavailable or unsafe")
        for path in (
            self.conversion_manifest,
            self.prompt_configuration,
            self.verifier_tests,
            self.ollama,
        ):
            if not path.is_file() or path.is_symlink():
                raise ValueError("specialist release file is unavailable or unsafe")

    @property
    def state_root(self) -> Path:
        """Return the product root whose storage unit owns the ``state/`` child."""
        return self.training_artifact

    def release_root(self, attempt_id: str) -> Path:
        if not attempt_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in attempt_id):
            raise ValueError("release attempt identity is invalid")
        return self.training_artifact / f"release-{attempt_id}"

    @property
    def training_jobs(self) -> Path:
        return self.training_artifact / "jobs"

    def _paths(self) -> tuple[Path, ...]:
        return (
            self.training_artifact,
            self.conversion_environment,
            self.conversion_manifest,
            self.llama_cpp,
            self.model_directory,
            self.prompt_configuration,
            self.verifier_tests,
            self.ollama,
        )
