"""Configuration values that bound verified code execution."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.core.execution.repair_context import RepairContext


@dataclass(frozen=True, slots=True)
class GenerationSettings:
    max_output_tokens: int
    keep_alive: str = "5m"
    temperature: float = 0.0
    seed: int | None = 42

    def __post_init__(self) -> None:
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        if not self.keep_alive.strip():
            raise ValueError("keep_alive must not be empty")
        if self.temperature < 0:
            raise ValueError("temperature cannot be negative")


@dataclass(frozen=True, slots=True)
class VerifiedCodePolicy:
    economical_expert_id: str
    generation: GenerationSettings
    repair_attempts: int = 1
    escalate_on_failure: bool = True
    escalation_expert_id: str | None = None
    escalation_repair_attempts: int = 1
    repair_guidance: str = ""
    repair_context: RepairContext = RepairContext()

    def __post_init__(self) -> None:
        if not self.economical_expert_id.strip():
            raise ValueError("economical_expert_id must not be empty")
        if self.repair_attempts < 0 or self.escalation_repair_attempts < 0:
            raise ValueError("repair attempt limits cannot be negative")
        if self.escalate_on_failure and not (self.escalation_expert_id or "").strip():
            raise ValueError("escalation requires escalation_expert_id")
