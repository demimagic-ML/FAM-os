"""Immutable, privacy-bounded Supervisor audit contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


AUDIT_CONTRACT_VERSION = "fam.supervisor.audit/v1alpha1"
GENESIS_AUDIT_DIGEST = "0" * 64
_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_RESOURCE_ID = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+$")
_REASON_CODE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class SupervisorAuditOperation(StrEnum):
    SERVICE_DECLARE = "service_declare"
    SERVICE_START = "service_start"
    SERVICE_STOP = "service_stop"
    SERVICE_STATUS = "service_status"
    APPLY_RESOURCE_LIMITS = "apply_resource_limits"
    GRANT_FILESYSTEM_ACCESS = "grant_filesystem_access"
    GRANT_DEVICE_ACCESS = "grant_device_access"
    REVOKE_ACCESS = "revoke_access"
    RECOVER_SERVICE = "recover_service"
    TERMINATE_SERVICE = "terminate_service"


class SupervisorAuditOutcome(StrEnum):
    REQUESTED = "requested"
    SUCCEEDED = "succeeded"
    DENIED = "denied"
    FAILED = "failed"
    COMPENSATED = "compensated"


@dataclass(frozen=True, slots=True)
class SupervisorAuditIntent:
    event_id: str
    operation_id: str
    occurred_at: datetime
    request_id: str
    authority_ref: str
    principal_id: str
    session_id: str
    service_id: str
    operation: SupervisorAuditOperation
    outcome: SupervisorAuditOutcome
    resource_id: str | None = None
    reason_code: str | None = None
    evidence_ref: str | None = None
    contract_version: str = AUDIT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        values = (
            self.event_id, self.operation_id, self.request_id, self.authority_ref,
            self.principal_id, self.session_id, self.service_id,
        )
        if any(not _IDENTITY.fullmatch(value) for value in values):
            raise ValueError("audit identity field is invalid")
        if not self.service_id.startswith("fam-"):
            raise ValueError("audit service is outside the FAM namespace")
        if self.occurred_at.tzinfo is None:
            raise ValueError("audit timestamp must be timezone-aware")
        if self.resource_id is not None and not _RESOURCE_ID.fullmatch(self.resource_id):
            raise ValueError("audit resource ID is invalid")
        for value in (self.reason_code, self.evidence_ref):
            if value is not None and not _REASON_CODE.fullmatch(value):
                raise ValueError("audit reason/evidence code is invalid")
        if self.contract_version != AUDIT_CONTRACT_VERSION:
            raise ValueError("unsupported audit contract version")


@dataclass(frozen=True, slots=True)
class SupervisorAuditRecord:
    sequence: int
    previous_digest: str
    digest: str
    intent: SupervisorAuditIntent

    def __post_init__(self) -> None:
        if self.sequence <= 0:
            raise ValueError("audit sequence must be positive")
        if not _DIGEST.fullmatch(self.previous_digest) or not _DIGEST.fullmatch(self.digest):
            raise ValueError("audit chain digest is invalid")


@dataclass(frozen=True, slots=True)
class AuditChainVerification:
    passed: bool
    record_count: int
    head_digest: str
    failure_sequence: int | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.record_count < 0 or not _DIGEST.fullmatch(self.head_digest):
            raise ValueError("audit verification summary is invalid")
        if self.passed and (self.failure_sequence is not None or self.reason_code is not None):
            raise ValueError("passing audit verification cannot contain failure")
        if not self.passed and (self.failure_sequence is None or self.reason_code is None):
            raise ValueError("failed audit verification requires failure evidence")
