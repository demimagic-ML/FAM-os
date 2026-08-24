"""Durable state for model generation before any candidate edit effect."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, positive, text
from fam_os.core.engineering.candidate_generation import GeneratedCandidatePlan
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class CandidateGenerationStatus(StrEnum):
    INTENT_RECORDED = "intent_recorded"
    PLAN_VALIDATED = "plan_validated"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CandidateGenerationRecord:
    generation_id: str
    definition_id: str
    task_id: str
    candidate_id: str
    session_id: str
    principal_id: str
    prompt_sha256: str
    context_sha256: str
    model_ref: str
    status: CandidateGenerationStatus
    attempt_count: int
    consumed_tokens: int
    consumed_wall_seconds: int
    revision: int
    created_at: datetime
    updated_at: datetime
    plan: GeneratedCandidatePlan | None = None
    failure_code: str | None = None
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "generation_id", "definition_id", "task_id", "candidate_id",
            "session_id", "principal_id", "model_ref",
        ):
            text(getattr(self, name), name)
        digest(self.prompt_sha256, "prompt_sha256", required=True)
        digest(self.context_sha256, "context_sha256", required=True)
        for name in (
            "attempt_count", "consumed_tokens", "consumed_wall_seconds", "revision",
        ):
            positive(getattr(self, name), name, allow_zero=True)
        aware(self.created_at, "created_at")
        aware(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("candidate generation update predates creation")
        if self.status is CandidateGenerationStatus.PLAN_VALIDATED and self.plan is None:
            raise ValueError("validated candidate generation requires a plan")
        if self.status is not CandidateGenerationStatus.PLAN_VALIDATED and self.plan is not None:
            raise ValueError("non-validated candidate generation cannot retain a plan")
        if self.status is CandidateGenerationStatus.FAILED:
            text(self.failure_code or "", "failure_code")
        elif self.failure_code is not None:
            raise ValueError("active candidate generation cannot have a failure code")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("candidate generation record version is unsupported")
