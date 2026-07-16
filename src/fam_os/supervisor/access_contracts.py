"""Provider-neutral device and filesystem access grant contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


_RESOURCE_ID = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+$")
_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


class AccessResourceKind(StrEnum):
    DEVICE = "device"
    FILESYSTEM = "filesystem"


class AccessMode(StrEnum):
    READ = "read"
    WRITE = "write"
    READ_WRITE = "read_write"


class AccessEvidenceStatus(StrEnum):
    GRANTED = "granted"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class AccessResourceDescriptor:
    resource_id: str
    kind: AccessResourceKind
    allowed_modes: tuple[AccessMode, ...]

    def __post_init__(self) -> None:
        _validate_resource_id(self.resource_id)
        if not self.allowed_modes or len(set(self.allowed_modes)) != len(self.allowed_modes):
            raise ValueError("access resource modes must be non-empty and unique")


@dataclass(frozen=True, slots=True)
class ServiceAccessGrant:
    grant_id: str
    authority_ref: str
    principal_id: str
    session_id: str
    service_id: str
    resource_id: str
    kind: AccessResourceKind
    mode: AccessMode
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        values = (
            self.grant_id,
            self.authority_ref,
            self.principal_id,
            self.session_id,
            self.service_id,
        )
        if any(not _IDENTITY.fullmatch(value) for value in values):
            raise ValueError("access grant identity field is invalid")
        if not self.service_id.startswith("fam-"):
            raise ValueError("access grant service is outside the FAM namespace")
        _validate_resource_id(self.resource_id)
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("access grant timestamps must be timezone-aware")
        if self.expires_at <= self.issued_at:
            raise ValueError("access grant expiry must follow issue time")

    def active_at(self, instant: datetime) -> bool:
        if instant.tzinfo is None:
            raise ValueError("access-check instant must be timezone-aware")
        return self.issued_at <= instant < self.expires_at


@dataclass(frozen=True, slots=True)
class AccessApplicationEvidence:
    grant_id: str
    service_id: str
    resource_id: str
    adapter_id: str
    status: AccessEvidenceStatus
    observed_at: datetime

    def __post_init__(self) -> None:
        values = (self.grant_id, self.service_id, self.resource_id, self.adapter_id)
        if any(not _IDENTITY.fullmatch(value) for value in values):
            raise ValueError("access evidence identity field is invalid")
        _validate_resource_id(self.resource_id)
        if self.observed_at.tzinfo is None:
            raise ValueError("access evidence timestamp must be timezone-aware")


def _validate_resource_id(resource_id: str) -> None:
    if not _RESOURCE_ID.fullmatch(resource_id) or ".." in resource_id:
        raise ValueError("access resource_id must be a namespaced opaque identifier")
