"""Output contract and release-safety invariants."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

from fam_os.core.contracts.failures import (
    DegradationDisposition,
    DegradationNotice,
    FailureEnvelope,
)
TASK_RESULT_CONTRACT_VERSION = "fam.core.task-result/v1alpha2"


class ResultStatus(StrEnum):
    """Terminal state exposed by FAM Core."""

    COMPLETED = "completed"
    VERIFIED = "verified"
    WITHHELD = "withheld"
    FAILED = "failed"


class ResultAssurance(StrEnum):
    UNVERIFIED = "unverified"
    GROUNDED = "grounded"
    VERIFIED = "verified"


class ResultKind(StrEnum):
    """Policy-owned semantic category for a user-visible outcome."""

    CONVERSATION_ANSWER = "conversation_answer"
    GROUNDED_ANSWER = "grounded_answer"
    ACTION_PROPOSAL = "action_proposal"
    ACTION_RECEIPT = "action_receipt"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"


@dataclass(frozen=True, slots=True)
class ResultCitation:
    """One verified claim-to-source byte-span exposed with a final result."""

    citation_id: str
    claim_id: str
    claim_text: str
    source_id: str
    source_locator: str
    source_content_sha256: str
    provenance_id: str
    start_character: int
    end_character: int
    quoted_text: str
    quoted_text_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "citation_id", "claim_id", "claim_text", "source_id",
            "source_locator", "provenance_id", "quoted_text",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise ValueError(f"result citation {name} must be strict nonempty text")
        if len(self.claim_text) > 32_768 or len(self.quoted_text) > 32_768:
            raise ValueError("result citation text exceeds its bound")
        _sha256(self.source_content_sha256, "source_content_sha256")
        _sha256(self.quoted_text_sha256, "quoted_text_sha256")
        if not 0 <= self.start_character < self.end_character:
            raise ValueError("result citation character span is invalid")
        digest = hashlib.sha256(self.quoted_text.encode("utf-8")).hexdigest()
        if digest != self.quoted_text_sha256:
            raise ValueError("result citation quote digest does not match")


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
    contract_version: str = TASK_RESULT_CONTRACT_VERSION
    assurance: ResultAssurance = ResultAssurance.UNVERIFIED
    citations: tuple[ResultCitation, ...] = ()
    result_kind: ResultKind = ResultKind.CONVERSATION_ANSWER

    def __post_init__(self) -> None:
        self._validate_identity()
        self._validate_evidence()
        self._validate_release()
        self._validate_failure()
        self._validate_degradations()
        self._validate_citations()

    def _validate_identity(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must not be empty")
        if self.contract_version != TASK_RESULT_CONTRACT_VERSION:
            raise ValueError("unsupported task result contract_version")
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
        if not isinstance(self.result_kind, ResultKind):
            raise ValueError("result kind is invalid")
        if self.status is ResultStatus.VERIFIED and self.assurance is ResultAssurance.UNVERIFIED:
            object.__setattr__(self, "assurance", ResultAssurance.VERIFIED)
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
        if self.verified != (self.assurance is ResultAssurance.VERIFIED):
            raise ValueError("verified result and assurance label must agree")
        if self.assurance is ResultAssurance.GROUNDED:
            if self.status is not ResultStatus.COMPLETED or not self.evidence_ids:
                raise ValueError("grounded assurance requires completed cited evidence")
        if self.status in {ResultStatus.WITHHELD, ResultStatus.FAILED} and not self.reason.strip():
            raise ValueError("withheld and failed results require a reason")
        if self.result_kind is ResultKind.ACTION_RECEIPT and (
            self.status is not ResultStatus.VERIFIED or not self.verified
        ):
            raise ValueError("action receipts require independently verified status")
        if self.result_kind is ResultKind.ACTION_PROPOSAL and self.status not in {
            ResultStatus.WITHHELD, ResultStatus.FAILED,
        }:
            raise ValueError("action proposals cannot claim successful execution")
        if self.result_kind is ResultKind.CAPABILITY_UNAVAILABLE:
            raise ValueError("capability-unavailable outcomes are admission results")
        if (
            self.result_kind is ResultKind.GROUNDED_ANSWER
            and self.assurance is ResultAssurance.UNVERIFIED
        ):
            raise ValueError("grounded answers require grounded or verified assurance")

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

    def _validate_citations(self) -> None:
        if any(not isinstance(item, ResultCitation) for item in self.citations):
            raise ValueError("result citations have an invalid type")
        identities = tuple(item.citation_id for item in self.citations)
        if len(set(identities)) != len(identities):
            raise ValueError("result citation IDs must be unique")
        if self.citations and self.status not in {
            ResultStatus.COMPLETED, ResultStatus.VERIFIED,
        }:
            raise ValueError("only successful results may expose citations")
        if self.citations and self.assurance is ResultAssurance.UNVERIFIED:
            raise ValueError("cited results require grounded or verified assurance")


def _sha256(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"result citation {name} must be lowercase SHA-256")
