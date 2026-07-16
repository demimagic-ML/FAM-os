"""Trusted evidence records and outcomes for terminal result assembly."""

from dataclasses import dataclass

from fam_os.core.contracts import DegradationNotice, TaskResult
from fam_os.core.lifecycle.contracts import PlanInstanceSnapshot


@dataclass(frozen=True, slots=True)
class CandidateEvidenceRecord:
    candidate_id: str
    request_id: str
    plan_id: str
    content: str

    def __post_init__(self) -> None:
        for name in ("candidate_id", "request_id", "plan_id", "content"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise ValueError(f"{name} must be strict nonempty text")


@dataclass(frozen=True, slots=True)
class AcceptanceEvidenceRecord:
    evidence_id: str
    candidate_id: str
    acceptance_ids: tuple[str, ...]
    passed: bool

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or not self.candidate_id.strip():
            raise ValueError("acceptance evidence identifiers must not be empty")
        if not self.acceptance_ids or len(set(self.acceptance_ids)) != len(self.acceptance_ids):
            raise ValueError("acceptance IDs must be nonempty and unique")


@dataclass(frozen=True, slots=True)
class FinalResultAssembly:
    snapshot: PlanInstanceSnapshot


@dataclass(frozen=True, slots=True)
class FinalResultOutcome:
    result: TaskResult | None = None
    rejection_code: str | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.rejection_code is None):
            raise ValueError("final result outcome requires result or rejection")
