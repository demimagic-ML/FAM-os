"""Durable expert residency state and lease contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


EXPERT_RESIDENCY_CONTRACT_VERSION = "fam.scheduler.expert-residency/v1alpha1"


class ExpertResidencyState(StrEnum):
    COLD = "cold"
    WARM = "warm"
    ACTIVE = "active"
    EVICTING = "evicting"


class ResidencyTransitionReason(StrEnum):
    REGISTERED_COLD = "registered_cold"
    PROVIDER_LOADED = "provider_loaded"
    PROVIDER_ABSENT = "provider_absent"
    PROVIDER_REFRESHED = "provider_refreshed"
    LEASE_ACQUIRED = "lease_acquired"
    LEASE_RELEASED = "lease_released"
    LEASES_EXPIRED = "leases_expired"
    EVICTION_STARTED = "eviction_started"
    EVICTION_CONFIRMED = "eviction_confirmed"
    EVICTION_ABORTED = "eviction_aborted"


@dataclass(frozen=True, slots=True)
class ExpertResidencyIdentity:
    expert_id: str
    runtime_artifact_id: str

    def __post_init__(self) -> None:
        _require_text(self.expert_id, "expert_id")
        _require_text(self.runtime_artifact_id, "runtime_artifact_id")


@dataclass(frozen=True, slots=True)
class ResidencyLease:
    lease_id: str
    request_id: str
    acquired_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.lease_id, "lease_id")
        _require_text(self.request_id, "request_id")
        _require_time(self.acquired_at, "acquired_at")
        _require_time(self.expires_at, "expires_at")
        if self.expires_at <= self.acquired_at:
            raise ValueError("residency lease must expire after acquisition")


@dataclass(frozen=True, slots=True)
class ExpertResidencyRecord:
    identity: ExpertResidencyIdentity
    state: ExpertResidencyState
    record_revision: int
    active_leases: tuple[ResidencyLease, ...]
    eviction_id: str | None
    provider_observed_at: datetime
    resident_bytes: int | None
    accelerator_bytes: int | None
    context_tokens: int | None
    transitioned_at: datetime
    transition_reason: ResidencyTransitionReason

    def __post_init__(self) -> None:
        if self.record_revision < 0:
            raise ValueError("residency record revision cannot be negative")
        _require_time(self.transitioned_at, "transitioned_at")
        _require_time(self.provider_observed_at, "provider_observed_at")
        values = (self.resident_bytes, self.accelerator_bytes, self.context_tokens)
        if any(value is not None and value < 0 for value in values):
            raise ValueError("residency provider measurements cannot be negative")
        lease_ids = tuple(item.lease_id for item in self.active_leases)
        request_ids = tuple(item.request_id for item in self.active_leases)
        if len(set(lease_ids)) != len(lease_ids) or len(set(request_ids)) != len(request_ids):
            raise ValueError("residency leases must have unique lease and request IDs")
        self._validate_state_shape()

    def _validate_state_shape(self) -> None:
        if (self.state is ExpertResidencyState.ACTIVE) != bool(self.active_leases):
            raise ValueError("active residency state must exactly match active leases")
        evicting = self.state is ExpertResidencyState.EVICTING
        if evicting != (self.eviction_id is not None):
            raise ValueError("evicting residency state must exactly match eviction identity")
        if self.eviction_id is not None:
            _require_text(self.eviction_id, "eviction_id")
        if self.state is ExpertResidencyState.COLD:
            if any(value is not None for value in (
                self.resident_bytes, self.accelerator_bytes, self.context_tokens
            )):
                raise ValueError("cold residency cannot retain loaded measurements")


@dataclass(frozen=True, slots=True)
class ExpertResidencyCatalog:
    catalog_id: str
    revision: int
    updated_at: datetime
    records: tuple[ExpertResidencyRecord, ...]
    contract_version: str = EXPERT_RESIDENCY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EXPERT_RESIDENCY_CONTRACT_VERSION:
            raise ValueError("unsupported expert residency contract_version")
        _require_text(self.catalog_id, "catalog_id")
        _require_time(self.updated_at, "updated_at")
        if self.revision < 0 or not self.records:
            raise ValueError("residency catalog requires revision and records")
        experts = tuple(item.identity.expert_id for item in self.records)
        artifacts = tuple(item.identity.runtime_artifact_id for item in self.records)
        if len(set(experts)) != len(experts) or len(set(artifacts)) != len(artifacts):
            raise ValueError("residency catalog identities must be unique")
        if experts != tuple(sorted(experts)):
            raise ValueError("residency catalog records must be sorted by expert_id")
        if any(item.transitioned_at > self.updated_at for item in self.records):
            raise ValueError("residency record transition cannot exceed catalog update time")

    def require(self, expert_id: str) -> ExpertResidencyRecord:
        for record in self.records:
            if record.identity.expert_id == expert_id:
                return record
        raise KeyError(expert_id)


def cold_record(
    identity: ExpertResidencyIdentity, observed_at: datetime
) -> ExpertResidencyRecord:
    return ExpertResidencyRecord(
        identity, ExpertResidencyState.COLD, 0, (), None, observed_at,
        None, None, None, observed_at, ResidencyTransitionReason.REGISTERED_COLD,
    )


def initial_cold_residency_catalog(
    catalog_id: str,
    identities: tuple[ExpertResidencyIdentity, ...],
    provider_absence_confirmed_at: datetime,
) -> ExpertResidencyCatalog:
    if not identities:
        raise ValueError("initial residency catalog requires identities")
    records = tuple(sorted(
        (cold_record(identity, provider_absence_confirmed_at) for identity in identities),
        key=lambda item: item.identity.expert_id,
    ))
    return ExpertResidencyCatalog(
        catalog_id, 0, provider_absence_confirmed_at, records
    )


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_time(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
