"""Privacy-bounded immutable audit values for application actions."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.applications.actions import ActionStatus
from fam_os.applications.identifiers import normalize_unique, require_identifier


APPLICATION_ACTION_AUDIT_VERSION = "fam.application.action-audit/v1alpha1"
GENESIS_ACTION_AUDIT_DIGEST = "0" * 64
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class ActionAuditStage(StrEnum):
    REQUESTED = "requested"
    PRECONDITION_FAILED = "precondition_failed"
    EXECUTION_FAILED = "execution_failed"
    POSTCONDITION_FAILED = "postcondition_failed"
    VERIFIED = "verified"


@dataclass(frozen=True, slots=True)
class ApplicationActionAuditIntent:
    event_id: str
    operation_id: str
    occurred_at: datetime
    request_id: str
    plan_instance_id: str
    principal_id: str
    session_id: str
    application_id: str
    instance_id: str
    capability_id: str
    permission_grant_id: str
    proposal_id: str
    confirmation_id: str
    stage: ActionAuditStage
    resource_sha256: str | None = None
    condition_ids: tuple[str, ...] = ()
    result_status: ActionStatus | None = None
    reversal_capability_id: str | None = None
    reversal_available: bool = False
    failure_code: str | None = None
    contract_version: str = APPLICATION_ACTION_AUDIT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "event_id", "operation_id", "request_id", "plan_instance_id",
            "principal_id", "session_id", "application_id", "instance_id",
            "capability_id", "permission_grant_id", "proposal_id", "confirmation_id",
        ):
            object.__setattr__(self, name, require_identifier(getattr(self, name), name))
        if self.occurred_at.tzinfo is None:
            raise ValueError("action audit timestamp must be timezone-aware")
        if self.resource_sha256 is not None and not _DIGEST.fullmatch(self.resource_sha256):
            raise ValueError("action audit resource digest is invalid")
        object.__setattr__(
            self, "condition_ids", normalize_unique(self.condition_ids, "condition_ids")
        )
        if self.reversal_capability_id is not None:
            object.__setattr__(
                self, "reversal_capability_id",
                require_identifier(self.reversal_capability_id, "reversal_capability_id"),
            )
        if self.reversal_available and self.reversal_capability_id is None:
            raise ValueError("available reversal requires a capability")
        if self.failure_code is not None:
            object.__setattr__(
                self, "failure_code", require_identifier(self.failure_code, "failure_code")
            )
        self._validate_stage()
        if self.contract_version != APPLICATION_ACTION_AUDIT_VERSION:
            raise ValueError("unsupported action audit contract version")

    def _validate_stage(self) -> None:
        if self.stage is ActionAuditStage.REQUESTED:
            if self.result_status is not None or self.failure_code is not None:
                raise ValueError("requested action audit cannot contain an outcome")
            return
        if self.result_status is None:
            raise ValueError("terminal action audit requires result status")
        if self.stage is ActionAuditStage.VERIFIED:
            if self.result_status is not ActionStatus.VERIFIED or self.failure_code is not None:
                raise ValueError("verified action audit has inconsistent outcome")
        elif self.failure_code is None or self.result_status is ActionStatus.VERIFIED:
            raise ValueError("failed action audit requires failure metadata")


@dataclass(frozen=True, slots=True)
class ApplicationActionAuditRecord:
    sequence: int
    previous_digest: str
    digest: str
    intent: ApplicationActionAuditIntent

    def __post_init__(self) -> None:
        if self.sequence <= 0:
            raise ValueError("action audit sequence must be positive")
        if not _DIGEST.fullmatch(self.previous_digest) or not _DIGEST.fullmatch(self.digest):
            raise ValueError("action audit chain digest is invalid")


@dataclass(frozen=True, slots=True)
class ApplicationActionAuditVerification:
    passed: bool
    record_count: int
    head_digest: str
    failure_sequence: int | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.record_count < 0 or not _DIGEST.fullmatch(self.head_digest):
            raise ValueError("action audit verification summary is invalid")
        if self.passed != (self.failure_sequence is None and self.reason_code is None):
            raise ValueError("action audit verification outcome is inconsistent")


class ApplicationAuditEmissionError(RuntimeError):
    pass


class ApplicationAuditIntegrityError(RuntimeError):
    pass
