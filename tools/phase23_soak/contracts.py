"""Typed settings and qualification thresholds for the installed soak."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


CONTRACT_VERSION = "fam.product.phase23-installed-soak/v1alpha1"
MINIMUM_QUALIFICATION_SECONDS = 86_400


@dataclass(frozen=True, slots=True)
class SoakSettings:
    repository: Path
    output_root: Path
    run_id: str
    duration_seconds: float = MINIMUM_QUALIFICATION_SECONDS
    request_interval_seconds: float = 300
    connector_interval_seconds: float = 14_400
    daemon_restart_interval_seconds: float = 21_600
    provider_crash_interval_seconds: float = 28_800
    ollama_url: str = "http://127.0.0.1:11435"
    owner_ollama_url: str = "http://127.0.0.1:11434"
    source_model_root: Path = Path("/usr/share/ollama/.ollama/models")
    full_model_pressure: bool = True

    def __post_init__(self) -> None:
        if not self.repository.is_absolute() or not self.repository.is_dir():
            raise ValueError("soak repository must be an absolute directory")
        if not self.output_root.is_absolute() or self.output_root.exists():
            raise ValueError("soak output root must be a new absolute path")
        if not self.source_model_root.is_absolute() or not self.source_model_root.is_dir():
            raise ValueError("soak model source root is unavailable")
        values = (
            self.duration_seconds,
            self.request_interval_seconds,
            self.connector_interval_seconds,
            self.daemon_restart_interval_seconds,
            self.provider_crash_interval_seconds,
        )
        if any(value <= 0 for value in values):
            raise ValueError("soak durations and cadences must be positive")
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789-"
        if not self.run_id or any(character not in allowed for character in self.run_id):
            raise ValueError("soak run identity is invalid")
        if not self.ollama_url.startswith("http://127.0.0.1:"):
            raise ValueError("managed soak Ollama must use loopback")
        if not self.owner_ollama_url.startswith("http://127.0.0.1:"):
            raise ValueError("owner Ollama must use loopback")

    @property
    def qualification_eligible(self) -> bool:
        return (
            self.duration_seconds >= MINIMUM_QUALIFICATION_SECONDS
            and self.full_model_pressure
        )


REQUIRED_EVENT_MINIMUMS = {
    "verified_inference": 2,
    "connector_churn": 1,
    "model_pressure": 1,
    "verifier_crash": 1,
    "ollama_crash": 1,
    "daemon_restart": 1,
    "low_disk_pressure": 1,
    "signed_update": 1,
    "signed_rollback": 1,
    "resource_sample": 2,
    "final_recovery": 1,
}

