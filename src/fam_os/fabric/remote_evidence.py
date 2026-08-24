"""Content-free durable evidence for one authenticated remote inference attempt."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum


REMOTE_EXECUTION_EVIDENCE_VERSION = "fam.fabric.remote-execution-evidence/v1alpha1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_TIERS = frozenset({"economical", "specialist", "escalation", "embedding"})


class RemoteEvidenceDisposition(StrEnum):
    AUTHENTICATED_CANDIDATE = "authenticated_candidate"
    RELEASED = "released"
    REJECTED = "rejected"
    WITHHELD = "withheld"


class RemoteVerificationOutcome(StrEnum):
    PENDING = "pending"
    NOT_REQUIRED = "not_required"
    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class RemoteExecutionEvidence:
    evidence_id: str
    instance_id: str
    request_id: str
    remote_plan_id: str
    remote_plan_sha256: str
    execution_id: str
    execution_request_sha256: str
    execution_result_sha256: str
    enrollment_id: str
    peer_device_id: str
    expert_id: str
    model_ref: str
    expert_tier: str
    capability_declaration_id: str
    context_evidence_id: str
    context_id: str
    context_content_bytes: int
    context_content_sha256: str
    context_receipt_sha256: str
    budget_reservation_id: str
    budget_attempt_id: str
    candidate_id: str
    candidate_sha256: str
    result_content_bytes: int
    result_content_sha256: str
    disposition: RemoteEvidenceDisposition
    verification_outcome: RemoteVerificationOutcome
    acceptance_id: str | None
    acceptance_evidence_id: str | None
    verification_run_id: str | None
    authenticated_at: datetime
    finalized_at: datetime | None
    raw_content_retained: bool = False
    partial_output_retained: bool = False
    contract_version: str = REMOTE_EXECUTION_EVIDENCE_VERSION

    def __post_init__(self) -> None:
        for name in (
            "evidence_id", "instance_id", "request_id", "remote_plan_id",
            "execution_id", "enrollment_id", "peer_device_id", "expert_id",
            "model_ref", "capability_declaration_id", "context_evidence_id",
            "context_id", "budget_reservation_id", "budget_attempt_id",
            "candidate_id",
        ):
            _identifier(getattr(self, name), name)
        for name in (
            "remote_plan_sha256", "execution_request_sha256",
            "execution_result_sha256", "context_content_sha256",
            "context_receipt_sha256", "candidate_sha256",
            "result_content_sha256",
        ):
            _digest(getattr(self, name), name)
        if self.expert_tier not in _TIERS:
            raise ValueError("remote evidence expert tier is invalid")
        if self.context_content_bytes <= 0 or self.result_content_bytes <= 0:
            raise ValueError("remote evidence byte counts must be positive")
        if self.candidate_sha256 != self.result_content_sha256:
            raise ValueError("remote candidate differs from authenticated result")
        if not isinstance(self.disposition, RemoteEvidenceDisposition):
            raise TypeError("remote evidence disposition is invalid")
        if not isinstance(self.verification_outcome, RemoteVerificationOutcome):
            raise TypeError("remote evidence verification outcome is invalid")
        _time(self.authenticated_at)
        if self.finalized_at is not None:
            _time(self.finalized_at)
            if self.finalized_at < self.authenticated_at:
                raise ValueError("remote evidence finalized before authentication")
        self._validate_outcome()
        if self.raw_content_retained or self.partial_output_retained:
            raise ValueError("remote execution evidence must be content-free and complete")
        if self.contract_version != REMOTE_EXECUTION_EVIDENCE_VERSION:
            raise ValueError("remote execution evidence contract is unsupported")

    def finalize(
        self,
        disposition: RemoteEvidenceDisposition,
        verification_outcome: RemoteVerificationOutcome,
        *,
        acceptance_id: str | None,
        acceptance_evidence_id: str | None,
        verification_run_id: str | None,
        finalized_at: datetime,
    ) -> RemoteExecutionEvidence:
        if self.disposition is not RemoteEvidenceDisposition.AUTHENTICATED_CANDIDATE:
            raise ValueError("remote execution evidence is already final")
        return replace(
            self,
            disposition=disposition,
            verification_outcome=verification_outcome,
            acceptance_id=acceptance_id,
            acceptance_evidence_id=acceptance_evidence_id,
            verification_run_id=verification_run_id,
            finalized_at=finalized_at,
        )

    def _validate_outcome(self) -> None:
        values = (
            self.acceptance_id,
            self.acceptance_evidence_id,
            self.verification_run_id,
        )
        for value in values:
            if value is not None:
                _identifier(value, "remote verification reference")
        if self.disposition is RemoteEvidenceDisposition.AUTHENTICATED_CANDIDATE:
            if self.verification_outcome is not RemoteVerificationOutcome.PENDING:
                raise ValueError("authenticated remote candidate must await policy")
            if any(value is not None for value in values) or self.finalized_at is not None:
                raise ValueError("pending remote evidence cannot have final references")
            return
        if self.finalized_at is None:
            raise ValueError("final remote evidence needs a final timestamp")
        if self.disposition is RemoteEvidenceDisposition.RELEASED:
            allowed = {
                RemoteVerificationOutcome.PASSED,
                RemoteVerificationOutcome.NOT_REQUIRED,
            }
            if self.verification_outcome not in allowed:
                raise ValueError("released remote evidence lacks acceptance")
            if self.verification_outcome is RemoteVerificationOutcome.PASSED and (
                self.acceptance_id is None or self.acceptance_evidence_id is None
            ):
                raise ValueError("verified remote release lacks acceptance evidence")
            if self.verification_outcome is RemoteVerificationOutcome.NOT_REQUIRED and any(
                value is not None for value in values
            ):
                raise ValueError("unverified remote release cannot claim verification")
            return
        if self.disposition is RemoteEvidenceDisposition.REJECTED:
            if self.verification_outcome is not RemoteVerificationOutcome.FAILED:
                raise ValueError("rejected remote evidence must bind failed verification")
            if self.acceptance_id is None:
                raise ValueError("rejected remote evidence lacks its acceptance policy")
            return
        if self.verification_outcome is not RemoteVerificationOutcome.UNAVAILABLE:
            raise ValueError("withheld remote evidence must bind unavailable verification")


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"remote evidence {name} is invalid")


def _digest(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"remote evidence {name} is not lowercase SHA-256")


def _time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("remote evidence timestamps must be timezone-aware")
