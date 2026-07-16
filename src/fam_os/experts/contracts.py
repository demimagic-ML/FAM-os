"""Provider-independent expert description."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.experts.capabilities import require_expert_capabilities


class ExpertTier(StrEnum):
    MICRO = "micro"
    ECONOMICAL = "economical"
    ESCALATION = "escalation"
    REMOTE = "remote"


class ExpertState(StrEnum):
    COLD = "cold"
    LOADING = "loading"
    RESIDENT = "resident"
    EVICTING = "evicting"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ExpertDescriptor:
    expert_id: str
    model_ref: str
    tier: ExpertTier
    capabilities: tuple[str, ...]
    max_context_tokens: int
    estimated_resident_bytes: int
    verifier_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.expert_id.strip() or not self.model_ref.strip():
            raise ValueError("expert_id and model_ref must not be empty")
        require_expert_capabilities(self.capabilities)
        if self.max_context_tokens <= 0:
            raise ValueError("max_context_tokens must be positive")
        if self.estimated_resident_bytes <= 0:
            raise ValueError("estimated_resident_bytes must be positive")
