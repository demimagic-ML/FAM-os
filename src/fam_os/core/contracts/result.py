"""Output contract and release-safety invariants."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.core.contracts.failures import (
    DegradationDisposition,
    DegradationNotice,
    FailureEnvelope,
)
from fam_os.core.contracts.version import CORE_CONTRACT_VERSION


class ResultStatus(StrEnum):
    """Terminal state exposed by FAM Core."""

    COMPLETED = "completed"
    VERIFIED = "verified"
    WITHHELD = "withheld"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TaskResult:
    """A final result; unverified required output can never carry content."""

    request_id: str
    status: ResultStatus
    content: str | None
    verified: bool = False
    reason: str = ""
    plan_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    failure: FailureEnvelope | None = None
    degradations: tuple[DegradationNotice, ...] = ()
    contract_version: str = CORE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        self._validate_identity()
        self._validate_evidence()
        self._validate_release()
        self._validate_failure()
        self._validate_degradations()

    def _validate_identity(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must not be empty")
        if not self.contract_version.strip():
            raise ValueError("contract_version must not be empty")
        if self.plan_id is not None and not self.plan_id.strip():
            raise ValueError("plan_id must not be empty")

    def _validate_evidence(self) -> None:
        evidence_ids = tuple(evidence_id.strip() for evidence_id in self.evidence_ids)
        if any(not evidence_id for evidence_id in evidence_ids):
            raise ValueError("evidence_ids must not be empty")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence_ids must be unique")
        object.__setattr__(self, "evidence_ids", evidence_ids)

    def _validate_release(self) -> None:
        if self.status is ResultStatus.VERIFIED and not self.verified:
            raise ValueError("verified status requires verified=True")
        if self.verified and self.status is not ResultStatus.VERIFIED:
            raise ValueError("verified=True requires verified status")
        if self.status in {ResultStatus.WITHHELD, ResultStatus.FAILED} and self.content is not None:
            raise ValueError("withheld and failed results cannot expose content")
        if self.status in {ResultStatus.COMPLETED, ResultStatus.VERIFIED} and not self.content:
            raise ValueError("successful results require content")
        if self.status is ResultStatus.VERIFIED and not self.evidence_ids:
            raise ValueError("verified results require evidence_ids")
        if self.status in {ResultStatus.WITHHELD, ResultStatus.FAILED} and not self.reason.strip():
            raise ValueError("withheld and failed results require a reason")

    def _validate_failure(self) -> None:
        successful = self.status in {ResultStatus.COMPLETED, ResultStatus.VERIFIED}
        if successful and self.failure is not None:
            raise ValueError("successful results cannot carry a failure")
        if self.status is ResultStatus.FAILED and self.failure is None:
            raise ValueError("failed results require a structured failure")
        if self.failure is None:
            return
        if self.reason.strip() != self.failure.safe_message:
            raise ValueError("result reason must match the failure safe_message")
        if not set(self.failure.evidence_ids) <= set(self.evidence_ids):
            raise ValueError("failure evidence must be linked by the task result")

    def _validate_degradations(self) -> None:
        degradation_ids = tuple(item.degradation_id for item in self.degradations)
        if len(set(degradation_ids)) != len(degradation_ids):
            raise ValueError("degradation IDs must be unique")
        linked_evidence = set(self.evidence_ids)
        if any(not set(item.evidence_ids) <= linked_evidence for item in self.degradations):
            raise ValueError("degradation evidence must be linked by the task result")
        withholding = tuple(
            item for item in self.degradations
            if item.disposition is DegradationDisposition.WITHHOLD
        )
        if self.status in {ResultStatus.COMPLETED, ResultStatus.VERIFIED} and withholding:
            raise ValueError("successful results cannot carry withholding degradations")
        if self.status is ResultStatus.WITHHELD and self.failure is None:
            if not withholding:
                raise ValueError("withheld result requires a failure or withholding degradation")
            if self.reason.strip() not in {item.safe_message for item in withholding}:
                raise ValueError("withheld reason must match a degradation safe_message")
