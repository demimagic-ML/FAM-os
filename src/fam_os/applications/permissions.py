"""Scoped permission grants for application capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fam_os.applications.identifiers import normalize_unique, require_identifier
from fam_os.applications.policy import ApplicationAuthority
from fam_os.applications.timestamps import require_aware_datetime


@dataclass(frozen=True, slots=True)
class PermissionScope:
    application_ids: tuple[str, ...] = ()
    instance_ids: tuple[str, ...] = ()
    capability_ids: tuple[str, ...] = ()
    resource_uris: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        identifier_fields = ("application_ids", "instance_ids", "capability_ids")
        for field_name in identifier_fields:
            values = tuple(
                require_identifier(value, field_name) for value in getattr(self, field_name)
            )
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must be unique")
            object.__setattr__(self, field_name, values)
        object.__setattr__(
            self,
            "resource_uris",
            normalize_unique(self.resource_uris, "resource_uris"),
        )
        if not any(getattr(self, field) for field in (*identifier_fields, "resource_uris")):
            raise ValueError("permission scope must constrain at least one target")


@dataclass(frozen=True, slots=True)
class PermissionGrant:
    grant_id: str
    subject_id: str
    authorities: tuple[ApplicationAuthority, ...]
    scope: PermissionScope
    issued_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "grant_id", require_identifier(self.grant_id, "grant_id"))
        object.__setattr__(self, "subject_id", require_identifier(self.subject_id, "subject_id"))
        if not self.authorities:
            raise ValueError("at least one authority is required")
        if len(set(self.authorities)) != len(self.authorities):
            raise ValueError("authorities must be unique")
        require_aware_datetime(self.issued_at, "issued_at")
        if self.expires_at is not None:
            require_aware_datetime(self.expires_at, "expires_at")
            if self.expires_at <= self.issued_at:
                raise ValueError("expires_at must be after issued_at")
        if self.revoked_at is not None:
            require_aware_datetime(self.revoked_at, "revoked_at")
            if self.revoked_at < self.issued_at:
                raise ValueError("revoked_at cannot be before issued_at")

    def active_at(self, instant: datetime) -> bool:
        require_aware_datetime(instant, "instant")
        return (
            instant >= self.issued_at
            and (self.expires_at is None or instant < self.expires_at)
            and (self.revoked_at is None or instant < self.revoked_at)
        )
