"""Expiry and deletion contracts for permissioned memory records."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

MEMORY_LIFECYCLE_CONTRACT_VERSION = "fam.memory.lifecycle/v1alpha1"


class MemoryExpiryState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    PURGED = "purged"


class MemoryDeletionReason(StrEnum):
    USER_REQUEST = "user_request"
    EXPIRY = "expiry"
    SCOPE_REVOKED = "scope_revoked"
    SOURCE_REMOVED = "source_removed"


@dataclass(frozen=True, slots=True)
class MemoryExpiryEvaluation:
    record_id: str
    expires_at: datetime
    evaluated_at: datetime
    state: MemoryExpiryState
    contract_version: str = MEMORY_LIFECYCLE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _texts(self.record_id)
        _aware(self.expires_at, "expires_at")
        _aware(self.evaluated_at, "evaluated_at")
        expected = MemoryExpiryState.ACTIVE if self.evaluated_at < self.expires_at else MemoryExpiryState.EXPIRED
        if self.state is MemoryExpiryState.PURGED:
            if self.evaluated_at < self.expires_at:
                raise ValueError("memory cannot be purged by expiry before expires_at")
        elif self.state is not expected:
            raise ValueError("memory expiry state must derive from evaluation time")


@dataclass(frozen=True, slots=True)
class MemoryDeletionRequest:
    request_id: str
    record_id: str
    owner_id: str
    requested_by: str
    requested_at: datetime
    reason: MemoryDeletionReason
    contract_version: str = MEMORY_LIFECYCLE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _texts(self.request_id, self.record_id, self.owner_id, self.requested_by)
        _aware(self.requested_at, "requested_at")


@dataclass(frozen=True, slots=True)
class MemoryDeletionReceipt:
    request_id: str
    record_id: str
    deleted_at: datetime
    deleted_content_sha256: str
    tombstone_sha256: str
    payload_removed: bool
    contract_version: str = MEMORY_LIFECYCLE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _texts(self.request_id, self.record_id)
        _aware(self.deleted_at, "deleted_at")
        for digest in (self.deleted_content_sha256, self.tombstone_sha256):
            if len(digest) != 64 or any(value not in "0123456789abcdef" for value in digest):
                raise ValueError("memory deletion digests must be lowercase SHA-256")
        if not self.payload_removed:
            raise ValueError("deletion receipt requires confirmed payload removal")


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")


def _texts(*values: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError("memory lifecycle identifiers must not be empty")
