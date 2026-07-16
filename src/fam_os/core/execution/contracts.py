"""Internal evidence and terminal-state contracts for verified execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.core.contracts.result import ResultStatus, TaskResult
from fam_os.routing.contracts import RoutingResult
from fam_os.telemetry.contracts import InferenceMetrics
from fam_os.verification.contracts import VerificationReport


class AttemptKind(StrEnum):
    ECONOMICAL = "economical"
    REPAIR = "repair"
    ESCALATION = "escalation"
    ESCALATION_REPAIR = "escalation_repair"


class ExecutionStatus(StrEnum):
    VERIFIED = "verified"
    VERIFIED_AFTER_REPAIR = "verified_after_repair"
    VERIFIED_AFTER_ESCALATION = "verified_after_escalation"
    VERIFIED_AFTER_ESCALATION_REPAIR = "verified_after_escalation_repair"
    ROUTE_NOT_SUPPORTED = "route_not_supported"
    VERIFICATION_FAILED = "verification_failed"
    ERROR = "error"

    @property
    def releases_content(self) -> bool:
        return self in {
            self.VERIFIED,
            self.VERIFIED_AFTER_REPAIR,
            self.VERIFIED_AFTER_ESCALATION,
            self.VERIFIED_AFTER_ESCALATION_REPAIR,
        }


@dataclass(frozen=True, slots=True)
class ExecutionAttempt:
    attempt_id: str
    kind: AttemptKind
    expert_id: str
    model_ref: str
    candidate: str
    metrics: InferenceMetrics
    verification: VerificationReport

    def __post_init__(self) -> None:
        if not self.attempt_id.strip() or not self.expert_id.strip() or not self.model_ref.strip():
            raise ValueError("attempt and expert identifiers must not be empty")
        if not self.candidate.strip():
            raise ValueError("candidate must not be empty")
        if self.metrics.model_ref != self.model_ref:
            raise ValueError("inference metrics must describe the attempt model")
        if self.verification.verification_id != self.attempt_id:
            raise ValueError("verification must describe the same attempt")


@dataclass(frozen=True, slots=True)
class VerifiedExecutionOutcome:
    request_id: str
    status: ExecutionStatus
    routing: RoutingResult
    result: TaskResult
    attempts: tuple[ExecutionAttempt, ...] = ()
    evicted_expert_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.request_id.strip() or self.result.request_id != self.request_id:
            raise ValueError("outcome and result request IDs must match")
        if len(set(self.evicted_expert_ids)) != len(self.evicted_expert_ids):
            raise ValueError("evicted expert IDs must be unique")
        if self.status.releases_content:
            self._validate_released_result()
        elif self.result.content is not None:
            raise ValueError("non-release outcomes cannot expose content")

    def _validate_released_result(self) -> None:
        if self.result.status is not ResultStatus.VERIFIED or not self.result.verified:
            raise ValueError("release outcomes require a verified task result")
        if not self.attempts or not self.attempts[-1].verification.passed:
            raise ValueError("release outcomes require a final passing attempt")
        evidence_id = self.attempts[-1].verification.verification_id
        if evidence_id not in self.result.evidence_ids:
            raise ValueError("released results must reference the passing verification")
        if self.result.content != self.attempts[-1].candidate:
            raise ValueError("released content must match the passing candidate")
