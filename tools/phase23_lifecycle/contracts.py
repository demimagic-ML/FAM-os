"""Typed inputs and result contract for Phase 23.8."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


CONTRACT_VERSION = "fam.product.phase23-installed-lifecycle/v1alpha1"


@dataclass(frozen=True, slots=True)
class LifecycleSettings:
    repository: Path
    output_root: Path
    run_id: str
    owner_ollama_url: str = "http://127.0.0.1:11434"
    model_ref: str = "qwen3:1.7b"
    console_port: int = 18765

    def __post_init__(self) -> None:
        if not self.repository.is_absolute() or not self.repository.is_dir():
            raise ValueError("lifecycle repository must be an absolute directory")
        if not self.output_root.is_absolute() or self.output_root.exists():
            raise ValueError("lifecycle output root must be a new absolute path")
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789-"
        if not self.run_id or any(character not in allowed for character in self.run_id):
            raise ValueError("lifecycle run identity is invalid")
        if not self.owner_ollama_url.startswith("http://127.0.0.1:"):
            raise ValueError("lifecycle Ollama endpoint must use loopback")
        if not 1024 <= self.console_port <= 65535:
            raise ValueError("lifecycle Console port is invalid")
