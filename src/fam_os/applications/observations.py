"""Authorized application observation requests and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from fam_os.applications.failures import ApplicationFailure, ApplicationFailureCategory
from fam_os.applications.identifiers import require_identifier, require_text
from fam_os.applications.payloads import JsonObject, freeze_payload
from fam_os.applications.timestamps import require_aware_datetime


class ObservationStatus(StrEnum):
    OBSERVED = "observed"
    DENIED = "denied"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ObservationRequest:
    request_id: str
    instance_id: str
    capability_id: str
    permission_grant_id: str
    parameters: JsonObject = field(default_factory=dict)
    resource_uri: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("request_id", "instance_id", "capability_id", "permission_grant_id"):
            object.__setattr__(
                self, field_name, require_identifier(getattr(self, field_name), field_name)
            )
        object.__setattr__(self, "parameters", freeze_payload(self.parameters))
        if self.resource_uri is not None:
            object.__setattr__(
                self, "resource_uri", require_text(self.resource_uri, "resource_uri")
            )


@dataclass(frozen=True, slots=True)
class ObservationResult:
    request_id: str
    status: ObservationStatus
    observed_at: datetime
    payload: JsonObject = field(default_factory=dict)
    resource_uri: str | None = None
    revision: str | None = None
    error: ApplicationFailure | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_identifier(self.request_id, "request_id"))
        require_aware_datetime(self.observed_at, "observed_at")
        object.__setattr__(self, "payload", freeze_payload(self.payload))
        for field_name in ("resource_uri", "revision"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, require_text(value, field_name))
        if self.status is ObservationStatus.OBSERVED:
            if self.error is not None:
                raise ValueError("observed results cannot carry an error")
        elif self.error is None:
            raise ValueError("non-observed results require an error")
        if self.status is ObservationStatus.DENIED and self.error is not None:
            if self.error.category is not ApplicationFailureCategory.PERMISSION_DENIED:
                raise ValueError("denied observations require permission-denied failure")
        if self.status is ObservationStatus.UNAVAILABLE and self.error is not None:
            if self.error.category is not ApplicationFailureCategory.UNAVAILABLE:
                raise ValueError("unavailable observations require unavailable failure")
        if self.status is not ObservationStatus.OBSERVED and self.payload:
            raise ValueError("non-observed results cannot expose payload")
