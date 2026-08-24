"""Frozen v1alpha1 task result retained for exact decoding and migration."""

from dataclasses import dataclass

from fam_os.core.contracts.failures import DegradationNotice, FailureEnvelope
from fam_os.core.contracts.result import (
    ResultAssurance,
    ResultKind,
    ResultStatus,
    TaskResult as CurrentTaskResult,
)


LEGACY_TASK_RESULT_VERSION = "fam.core/v1alpha1"


@dataclass(frozen=True, slots=True)
class TaskResult:
    request_id: str
    status: ResultStatus
    content: str | None
    verified: bool = False
    reason: str = ""
    plan_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    failure: FailureEnvelope | None = None
    degradations: tuple[DegradationNotice, ...] = ()
    contract_version: str = LEGACY_TASK_RESULT_VERSION

    def __post_init__(self) -> None:
        if not self.request_id.strip() or self.contract_version != LEGACY_TASK_RESULT_VERSION:
            raise ValueError("legacy task result identity is invalid")
        if self.plan_id is not None and not self.plan_id.strip():
            raise ValueError("legacy task result plan identity is invalid")
        if len(set(self.evidence_ids)) != len(self.evidence_ids) or any(
            not item.strip() for item in self.evidence_ids
        ):
            raise ValueError("legacy task result evidence is invalid")
        successful = self.status in {ResultStatus.COMPLETED, ResultStatus.VERIFIED}
        if successful != bool(self.content):
            raise ValueError("legacy task result content does not match status")
        if self.verified != (self.status is ResultStatus.VERIFIED):
            raise ValueError("legacy task result verification is invalid")
        if self.status is ResultStatus.VERIFIED and not self.evidence_ids:
            raise ValueError("legacy verified result requires evidence")
        if not successful and not self.reason.strip():
            raise ValueError("legacy non-success result requires a reason")
        if self.status is ResultStatus.FAILED and self.failure is None:
            raise ValueError("legacy failed result requires a failure")
        if successful and self.failure is not None:
            raise ValueError("legacy successful result cannot carry a failure")


def migrate_task_result_v1alpha1(value: TaskResult) -> CurrentTaskResult:
    """Explicitly classify an old result without inventing action authority."""

    return CurrentTaskResult(
        value.request_id, value.status, value.content, value.verified,
        value.reason, value.plan_id, value.evidence_ids, value.failure,
        value.degradations,
        assurance=(
            ResultAssurance.VERIFIED if value.verified
            else ResultAssurance.UNVERIFIED
        ),
        result_kind=ResultKind.CONVERSATION_ANSWER,
    )
