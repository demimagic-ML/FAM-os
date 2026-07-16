"""Immutable Core request identity, authority, and admission evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from fam_os.core.contracts import FailureEnvelope, TaskRequest


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_MAX_CAPABILITIES = 256


@dataclass(frozen=True, slots=True)
class RequestIdentity:
    principal_id: str
    session_id: str
    authority_ref: str

    def __post_init__(self) -> None:
        _require_identities(
            self.principal_id, self.session_id, self.authority_ref
        )


@dataclass(frozen=True, slots=True)
class RequestAuthorityGrant:
    authority_ref: str
    principal_id: str
    session_id: str
    granted_capabilities: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_identities(
            self.authority_ref, self.principal_id, self.session_id
        )
        _require_aware(self.issued_at)
        _require_aware(self.expires_at)
        if self.expires_at <= self.issued_at:
            raise ValueError("authority expiry must follow issue time")
        if self.revoked_at is not None:
            _require_aware(self.revoked_at)
            if self.revoked_at < self.issued_at:
                raise ValueError("authority revocation predates issue time")
        _require_capabilities(self.granted_capabilities)
        object.__setattr__(
            self, "granted_capabilities",
            tuple(sorted(self.granted_capabilities)),
        )

    def active_at(self, instant: datetime) -> bool:
        _require_aware(instant)
        return (
            self.issued_at <= instant < self.expires_at
            and (self.revoked_at is None or instant < self.revoked_at)
        )


@dataclass(frozen=True, slots=True)
class RequestPermissionContext:
    principal_id: str
    session_id: str
    authority_ref: str
    authorized_capabilities: tuple[str, ...]
    valid_until: datetime

    def __post_init__(self) -> None:
        _require_identities(
            self.principal_id, self.session_id, self.authority_ref
        )
        _require_capabilities(self.authorized_capabilities)
        _require_aware(self.valid_until)


@dataclass(frozen=True, slots=True)
class AdmittedTaskRequest:
    admission_id: str
    request: TaskRequest
    permission: RequestPermissionContext
    admitted_at: datetime

    def __post_init__(self) -> None:
        _require_identities(self.admission_id)
        _require_aware(self.admitted_at)
        if self.admitted_at >= self.permission.valid_until:
            raise ValueError("admission must precede permission expiry")
        if self.permission.authorized_capabilities != self.request.required_capabilities:
            raise ValueError("admission permission must be least-privilege exact")


@dataclass(frozen=True, slots=True)
class RequestAdmissionOutcome:
    request_id: str
    admitted: AdmittedTaskRequest | None = None
    failure: FailureEnvelope | None = None

    def __post_init__(self) -> None:
        _require_identities(self.request_id)
        if (self.admitted is None) == (self.failure is None):
            raise ValueError("admission outcome requires exactly one result")
        if self.admitted is not None:
            if self.admitted.request.request_id != self.request_id:
                raise ValueError("admitted request identity does not match outcome")

    @property
    def accepted(self) -> bool:
        return self.admitted is not None


def _require_identities(*values: str) -> None:
    if any(not _IDENTIFIER.fullmatch(value) for value in values):
        raise ValueError("request admission identity is invalid")


def _require_capabilities(values: tuple[str, ...]) -> None:
    if len(values) > _MAX_CAPABILITIES:
        raise ValueError("request authority has too many capabilities")
    if any(not _IDENTIFIER.fullmatch(value) for value in values):
        raise ValueError("request authority capability is invalid")
    if len(set(values)) != len(values):
        raise ValueError("request authority capabilities must be unique")


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None:
        raise ValueError("request admission timestamp must be timezone-aware")
