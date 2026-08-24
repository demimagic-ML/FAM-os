"""Content-free reconciliation evidence for a lost remote inference attempt."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum


REMOTE_RECOVERY_EVIDENCE_VERSION = "fam.fabric.remote-recovery-evidence/v1alpha1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_TIERS = frozenset({"economical", "specialist", "escalation", "embedding"})


class RemoteAttemptFailure(StrEnum):
    DISCONNECTED = "disconnected"
    TIMEOUT = "timeout"
    PARTIAL_RESULT = "partial_result"
    UNCERTAIN_COMPLETION = "uncertain_completion"
    REMOTE_PROVIDER_FAILED = "remote_provider_failed"
    AUTHORITY_CHANGED = "authority_changed"
    AUTHENTICATION_FAILED = "authentication_failed"
    INVALID_RESULT = "invalid_result"


class RemoteRecoveryDisposition(StrEnum):
    LOCAL_RETRY_PENDING = "local_retry_pending"
    RECOVERED = "recovered"
    LOCAL_RETRY_FAILED = "local_retry_failed"
    RETRY_DENIED = "retry_denied"


@dataclass(frozen=True, slots=True)
class RemoteRecoveryEvidence:
    evidence_id: str
    instance_id: str
    request_id: str
    remote_plan_id: str
    remote_budget_reservation_id: str
    remote_attempt_id: str
    failure: RemoteAttemptFailure
    accepted_contract_sha256: str
    observed_contract_sha256: str
    unchanged_acceptance: bool
    local_retry_allowed: bool
    local_selection_id: str | None
    local_model_ref: str | None
    local_expert_tier: str | None
    local_budget_reservation_id: str | None
    local_attempt_id: str | None
    local_candidate_id: str | None
    disposition: RemoteRecoveryDisposition
    reason_codes: tuple[str, ...]
    detected_at: datetime
    finalized_at: datetime | None
    raw_content_retained: bool = False
    partial_output_retained: bool = False
    contract_version: str = REMOTE_RECOVERY_EVIDENCE_VERSION

    def __post_init__(self) -> None:
        for name in (
            "evidence_id", "instance_id", "request_id", "remote_plan_id",
            "remote_budget_reservation_id", "remote_attempt_id",
        ):
            _identifier(getattr(self, name), name)
        _digest(self.accepted_contract_sha256, "accepted_contract_sha256")
        _digest(self.observed_contract_sha256, "observed_contract_sha256")
        if not isinstance(self.failure, RemoteAttemptFailure):
            raise TypeError("remote recovery failure is invalid")
        if not isinstance(self.disposition, RemoteRecoveryDisposition):
            raise TypeError("remote recovery disposition is invalid")
        if self.unchanged_acceptance != (
            self.accepted_contract_sha256 == self.observed_contract_sha256
        ):
            raise ValueError("remote recovery acceptance comparison is inconsistent")
        local_values = (
            self.local_selection_id, self.local_model_ref,
            self.local_expert_tier, self.local_budget_reservation_id,
            self.local_attempt_id,
        )
        has_local = all(value is not None for value in local_values)
        if any(value is not None for value in local_values) != has_local:
            raise ValueError("remote recovery local retry identity is incomplete")
        if has_local:
            for value in local_values:
                assert value is not None
                _identifier(value, "local retry identity")
            if self.local_expert_tier not in _TIERS:
                raise ValueError("remote recovery local expert tier is invalid")
        if self.local_candidate_id is not None:
            _identifier(self.local_candidate_id, "local_candidate_id")
        if not self.reason_codes or len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("remote recovery reason codes must be nonempty and unique")
        for reason in self.reason_codes:
            _identifier(reason, "reason code")
        _time(self.detected_at)
        if self.finalized_at is not None:
            _time(self.finalized_at)
            if self.finalized_at < self.detected_at:
                raise ValueError("remote recovery finalized before detection")
        self._validate_disposition(has_local)
        if self.raw_content_retained or self.partial_output_retained:
            raise ValueError("remote recovery evidence must be content-free")
        if self.contract_version != REMOTE_RECOVERY_EVIDENCE_VERSION:
            raise ValueError("remote recovery evidence contract is unsupported")

    def recovered(
        self,
        candidate_id: str,
        finalized_at: datetime,
    ) -> RemoteRecoveryEvidence:
        if self.disposition is not RemoteRecoveryDisposition.LOCAL_RETRY_PENDING:
            raise ValueError("remote recovery is not awaiting a local candidate")
        return replace(
            self,
            local_candidate_id=candidate_id,
            disposition=RemoteRecoveryDisposition.RECOVERED,
            finalized_at=finalized_at,
        )

    def local_failed(self, finalized_at: datetime) -> RemoteRecoveryEvidence:
        if self.disposition is not RemoteRecoveryDisposition.LOCAL_RETRY_PENDING:
            raise ValueError("remote recovery is not awaiting a local candidate")
        return replace(
            self,
            disposition=RemoteRecoveryDisposition.LOCAL_RETRY_FAILED,
            finalized_at=finalized_at,
        )

    def _validate_disposition(self, has_local: bool) -> None:
        pending = self.disposition is RemoteRecoveryDisposition.LOCAL_RETRY_PENDING
        recovered = self.disposition is RemoteRecoveryDisposition.RECOVERED
        failed = self.disposition is RemoteRecoveryDisposition.LOCAL_RETRY_FAILED
        denied = self.disposition is RemoteRecoveryDisposition.RETRY_DENIED
        if pending:
            if not (self.unchanged_acceptance and self.local_retry_allowed and has_local):
                raise ValueError("pending local recovery lacks unchanged acceptance")
            if self.local_candidate_id is not None or self.finalized_at is not None:
                raise ValueError("pending local recovery cannot be final")
        elif recovered:
            if not (self.unchanged_acceptance and self.local_retry_allowed and has_local):
                raise ValueError("recovered remote attempt lacks valid local retry")
            if self.local_candidate_id is None or self.finalized_at is None:
                raise ValueError("recovered remote attempt lacks final candidate")
        elif failed:
            if not (self.local_retry_allowed and has_local):
                raise ValueError("failed local recovery lacks reserved retry")
            if self.local_candidate_id is not None or self.finalized_at is None:
                raise ValueError("failed local recovery has invalid final state")
        elif denied:
            if self.local_retry_allowed or has_local or self.local_candidate_id is not None:
                raise ValueError("denied remote recovery cannot claim a local retry")
            if self.finalized_at is None:
                raise ValueError("denied remote recovery must be final")


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"remote recovery {name} is invalid")


def _digest(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"remote recovery {name} is not lowercase SHA-256")


def _time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("remote recovery timestamps must be timezone-aware")
