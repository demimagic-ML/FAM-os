"""Verifier results consumed by orchestration policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class VerificationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class VerificationRequest:
    verification_id: str
    candidate: str

    def __post_init__(self) -> None:
        if not self.verification_id.strip():
            raise ValueError("verification_id must not be empty")
        if not self.candidate.strip():
            raise ValueError("candidate must not be empty")


@dataclass(frozen=True, slots=True)
class VerificationEvidence:
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    normalized_candidate: str | None = None
    isolation: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationReport:
    verification_id: str
    verifier_id: str
    status: VerificationStatus
    stage: str
    reason: str
    wall_seconds: float
    evidence: VerificationEvidence | None = None

    def __post_init__(self) -> None:
        if not self.verification_id.strip() or not self.verifier_id.strip():
            raise ValueError("verification_id and verifier_id must not be empty")
        if not self.stage.strip() or not self.reason.strip():
            raise ValueError("stage and reason must not be empty")
        if not isfinite(self.wall_seconds) or self.wall_seconds < 0:
            raise ValueError("wall_seconds cannot be negative")

    @property
    def passed(self) -> bool:
        return self.status is VerificationStatus.PASSED

    def failure_details(self, maximum_characters: int = 4_000) -> str:
        if maximum_characters <= 0:
            raise ValueError("maximum_characters must be positive")
        evidence = self.evidence or VerificationEvidence()
        details = evidence.stderr.strip() or evidence.stdout.strip() or self.reason
        return details[-maximum_characters:]
