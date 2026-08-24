"""Durable owner authority and audit receipts for specialist lifecycle changes."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


FACTORY_SPECIALIST_LIFECYCLE_VERSION = (
    "fam.factory.specialist-lifecycle/v1alpha1"
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


class FactorySpecialistLifecycleAction(StrEnum):
    MANUAL_ROLLBACK = "manual_rollback"
    FORCED_REGRESSION_ROLLBACK = "forced_regression_rollback"
    RETIRE = "retire"


@dataclass(frozen=True, slots=True)
class FactorySpecialistLifecycleRequest:
    request_id: str
    action: FactorySpecialistLifecycleAction
    release_id: str
    target_release_id: str | None
    expected_lifecycle_revision: int
    reason_code: str
    regression_evidence_sha256: str | None
    remove_artifact: bool
    issued_at: datetime
    request_sha256: str
    contract_version: str = FACTORY_SPECIALIST_LIFECYCLE_VERSION

    def __post_init__(self) -> None:
        for value in (self.request_id, self.release_id, self.reason_code):
            _identifier(value)
        if self.target_release_id is not None:
            _identifier(self.target_release_id)
        if self.expected_lifecycle_revision < 0:
            raise ValueError("specialist lifecycle revision is invalid")
        if self.action is FactorySpecialistLifecycleAction.RETIRE:
            if self.target_release_id is not None:
                raise ValueError("retirement cannot name a rollback target")
        elif self.remove_artifact:
            raise ValueError("rollback cannot remove the candidate artifact")
        if self.action is FactorySpecialistLifecycleAction.FORCED_REGRESSION_ROLLBACK:
            if self.regression_evidence_sha256 is None:
                raise ValueError("forced rollback requires regression evidence")
        elif self.regression_evidence_sha256 is not None:
            raise ValueError("only forced rollback may bind regression evidence")
        if self.regression_evidence_sha256 is not None:
            _sha(self.regression_evidence_sha256)
        _aware(self.issued_at)
        _sha(self.request_sha256)
        if self.request_sha256 != specialist_lifecycle_request_digest(self):
            raise ValueError("specialist lifecycle request digest does not match")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class FactorySpecialistLifecycleReceipt:
    receipt_id: str
    request_id: str
    request_sha256: str
    action: FactorySpecialistLifecycleAction
    release_id: str
    target_release_id: str | None
    reason_code: str
    lifecycle_revision: int
    active_release_id: str | None
    runtime_model_removed: bool
    artifact_removed: bool
    audit_retained: bool
    completed_at: datetime
    receipt_sha256: str
    contract_version: str = FACTORY_SPECIALIST_LIFECYCLE_VERSION

    def __post_init__(self) -> None:
        for value in (
            self.receipt_id, self.request_id, self.release_id, self.reason_code,
        ):
            _identifier(value)
        for optional_value in (self.target_release_id, self.active_release_id):
            if optional_value is not None:
                _identifier(optional_value)
        if self.lifecycle_revision < 1 or not self.audit_retained:
            raise ValueError("specialist lifecycle receipt state is invalid")
        if (
            self.action is not FactorySpecialistLifecycleAction.RETIRE
            and self.artifact_removed
        ):
            raise ValueError("rollback receipt cannot remove an artifact")
        _sha(self.request_sha256)
        _sha(self.receipt_sha256)
        _aware(self.completed_at)
        if self.receipt_sha256 != specialist_lifecycle_receipt_digest(self):
            raise ValueError("specialist lifecycle receipt digest does not match")
        _version(self.contract_version)


def build_specialist_lifecycle_request(
    **values: object,
) -> FactorySpecialistLifecycleRequest:
    document = dict(values)
    document["request_sha256"] = _digest(document)
    return FactorySpecialistLifecycleRequest(**document)  # type: ignore[arg-type]


def build_specialist_lifecycle_receipt(
    **values: object,
) -> FactorySpecialistLifecycleReceipt:
    document = dict(values)
    document["receipt_sha256"] = _digest(document)
    return FactorySpecialistLifecycleReceipt(**document)  # type: ignore[arg-type]


def specialist_lifecycle_request_digest(
    value: FactorySpecialistLifecycleRequest,
) -> str:
    return _digest(_without(_fields(value), "request_sha256", "contract_version"))


def specialist_lifecycle_receipt_digest(
    value: FactorySpecialistLifecycleReceipt,
) -> str:
    return _digest(_without(_fields(value), "receipt_sha256", "contract_version"))


def _fields(value: object) -> dict[str, object]:
    return {
        name: getattr(value, name)
        for name in value.__dataclass_fields__  # type: ignore[attr-defined]
    }


def _without(values: dict[str, object], *names: str) -> dict[str, object]:
    return {name: item for name, item in values.items() if name not in names}


def _canonical(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {name: _canonical(item) for name, item in value.items()}
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def _identifier(value: str) -> None:
    if _ID.fullmatch(value) is None:
        raise ValueError("specialist lifecycle identifier is invalid")


def _sha(value: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError("specialist lifecycle digest must be lowercase SHA-256")


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("specialist lifecycle timestamp must be timezone-aware")


def _version(value: str) -> None:
    if value != FACTORY_SPECIALIST_LIFECYCLE_VERSION:
        raise ValueError("unsupported specialist lifecycle contract version")
