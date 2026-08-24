"""Typed inputs for the installed dual-profile hardware matrix."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class HardwareMatrixSettings:
    repository: Path
    output_root: Path
    run_id: str
    source_model_root: Path
    owner_ollama_url: str = "http://127.0.0.1:11434"
    quiesce_owner_models: bool = False

    def __post_init__(self) -> None:
        if not self.repository.is_absolute() or not self.repository.is_dir():
            raise ValueError("hardware matrix repository must be an absolute directory")
        if not self.output_root.is_absolute() or self.output_root.exists():
            raise ValueError("hardware matrix output must be a new absolute path")
        if not self.source_model_root.is_absolute() or not self.source_model_root.is_dir():
            raise ValueError("hardware matrix source model root is unavailable")
        if not self.owner_ollama_url.startswith("http://127.0.0.1:"):
            raise ValueError("hardware matrix owner Ollama must use loopback HTTP")
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789-"
        if not self.run_id or any(character not in allowed for character in self.run_id):
            raise ValueError("hardware matrix run identity is invalid")
