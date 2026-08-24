"""Privacy-minimized learning records derived from verified terminal outcomes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


VERIFIED_LEARNING_CONTRACT_VERSION = "fam.adaptation.verified-learning/v1alpha1"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_INTENTS = frozenset({
    "conversation", "grounded_question", "read_only_task",
    "application_mutation", "code", "math", "retrieval", "media",
    "administration",
})
_TIERS = frozenset({
    "economical", "specialist", "escalation", "embedding", "deterministic",
})


@dataclass(frozen=True, slots=True)
class VerifiedLearningOutcome:
    learning_id: str
    workflow_id: str
    intent: str
    expert_id: str
    expert_tier: str
    observed_at: datetime
    context_token_bucket: int
    escalation_used: bool
    acceptance_evidence_id: str
    candidate_evidence_id: str
    evidence_sha256: str
    verified: bool = True
    local_only: bool = True
    prompt_retained: bool = False
    candidate_content_retained: bool = False
    source_content_retained: bool = False
    application_payload_retained: bool = False
    contract_version: str = VERIFIED_LEARNING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "learning_id", "workflow_id", "expert_id",
            "acceptance_evidence_id", "candidate_evidence_id",
        ):
            if not _IDENTIFIER.fullmatch(getattr(self, name)):
                raise ValueError(f"verified learning {name} is invalid")
        if self.intent not in _INTENTS or self.workflow_id != f"intent:{self.intent}":
            raise ValueError("verified learning workflow is not a closed intent bucket")
        if self.expert_tier not in _TIERS:
            raise ValueError("verified learning expert tier is invalid")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("verified learning time must be timezone-aware")
        if not _power_of_two(self.context_token_bucket):
            raise ValueError("verified learning context bucket must be a power of two")
        if not 128 <= self.context_token_bucket <= 32_768:
            raise ValueError("verified learning context bucket is outside policy")
        if not _sha256(self.evidence_sha256):
            raise ValueError("verified learning evidence must be lowercase SHA-256")
        retained = (
            self.prompt_retained, self.candidate_content_retained,
            self.source_content_retained, self.application_payload_retained,
        )
        if not self.verified or not self.local_only or any(retained):
            raise ValueError("learning must be verified, local, and content-free")
        if self.contract_version != VERIFIED_LEARNING_CONTRACT_VERSION:
            raise ValueError("verified learning contract version is unsupported")


def context_token_bucket(prompt: str) -> int:
    """Reduce prompt length to a conservative non-identifying power-of-two bucket."""
    estimated = max(1, (len(prompt) + 3) // 4)
    return min(32_768, max(128, 1 << (estimated - 1).bit_length()))


def _power_of_two(value: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0 and not value & (value - 1)


def _sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
