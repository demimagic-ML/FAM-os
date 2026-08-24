"""Restart policy for safe reads, inference, and mutation requests."""

from dataclasses import dataclass
from enum import StrEnum


REQUEST_RECOVERY_VERSION = "fam.product.request-recovery/v1alpha1"


class RequestWorkKind(StrEnum):
    READ_ONLY = "read_only"
    INFERENCE = "inference"
    MUTATION = "mutation"


class RecoverableRequestState(StrEnum):
    ACTIVE = "active"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETE = "complete"
    FAILED = "failed"


class RequestRestartDisposition(StrEnum):
    RESUME_SAFE = "resume_safe"
    REQUIRE_FRESH_APPROVAL = "require_fresh_approval"
    RETAIN_TERMINAL = "retain_terminal"


@dataclass(frozen=True, slots=True)
class RequestRecoveryRecord:
    request_id: str
    work_kind: RequestWorkKind
    state: RecoverableRequestState
    contract_version: str = REQUEST_RECOVERY_VERSION

    def __post_init__(self) -> None:
        if not self.request_id.strip() or self.contract_version != REQUEST_RECOVERY_VERSION:
            raise ValueError("request recovery record is invalid")


@dataclass(frozen=True, slots=True)
class RequestRestartDecision:
    request_id: str
    disposition: RequestRestartDisposition
    authority_retained: bool
    contract_version: str = REQUEST_RECOVERY_VERSION


def request_restart_decision(record: RequestRecoveryRecord) -> RequestRestartDecision:
    if record.state in {RecoverableRequestState.COMPLETE, RecoverableRequestState.FAILED}:
        disposition = RequestRestartDisposition.RETAIN_TERMINAL
    elif record.work_kind in {RequestWorkKind.READ_ONLY, RequestWorkKind.INFERENCE}:
        disposition = RequestRestartDisposition.RESUME_SAFE
    else:
        disposition = RequestRestartDisposition.REQUIRE_FRESH_APPROVAL
    return RequestRestartDecision(record.request_id, disposition, False)
