"""Typed settings and required scenarios for the installed matrix."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class InstalledScenario(StrEnum):
    LOCAL = "local"
    APPLICATION = "application"
    MEMORY = "memory"
    ESCALATION = "escalation"
    REMOTE = "remote"
    MEDIA = "media"
    FACTORY = "factory"


REQUIRED_SCENARIOS = tuple(InstalledScenario)


@dataclass(frozen=True, slots=True)
class InstalledMatrixSettings:
    repository: Path
    output_root: Path
    run_id: str
    ollama_url: str = "http://127.0.0.1:11434"
    source_model_root: Path = Path("/usr/share/ollama/.ollama/models")

    def __post_init__(self) -> None:
        if not self.repository.is_absolute() or not self.repository.is_dir():
            raise ValueError("installed matrix repository must be an absolute directory")
        if not self.output_root.is_absolute() or self.output_root.exists():
            raise ValueError("installed matrix output must be a new absolute path")
        if not self.source_model_root.is_absolute() or not self.source_model_root.is_dir():
            raise ValueError("installed matrix model root is unavailable")
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789-"
        if not self.run_id or any(character not in allowed for character in self.run_id):
            raise ValueError("installed matrix run identity is invalid")

