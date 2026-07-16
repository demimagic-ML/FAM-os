"""Tier-separated cache telemetry and deterministic retention contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


CACHE_POLICY_CONTRACT_VERSION = "fam.scheduler.cache-policy/v1alpha1"
CACHE_POLICY_VERSION = "fam.scheduler.cache-retention-policy/v1"


class CacheTier(StrEnum):
    HOST_PAGE_CACHE = "host_page_cache"
    PROVIDER_WEIGHTS = "provider_weights"
    ACCELERATOR_WEIGHTS = "accelerator_weights"
    NPU_COMPILED = "npu_compiled"


class CacheEntryState(StrEnum):
    COLD = "cold"
    WARM = "warm"
    ACTIVE = "active"


@dataclass(frozen=True, slots=True)
class CacheTelemetryEntry:
    artifact_id: str
    tier: CacheTier
    state: CacheEntryState
    artifact_bytes: int
    observed_bytes: int
    hit_count: int
    miss_count: int
    last_accessed_at: datetime | None
    reload_cost_ms: float
    evictable: bool
    source_evidence_digest_sha256: str

    def __post_init__(self) -> None:
        _text(self.artifact_id, "artifact_id")
        _digest(self.source_evidence_digest_sha256)
        if self.artifact_bytes <= 0 or not 0 <= self.observed_bytes <= self.artifact_bytes:
            raise ValueError("cache byte telemetry is invalid")
        if self.hit_count < 0 or self.miss_count < 0 or self.reload_cost_ms < 0:
            raise ValueError("cache counters and reload cost cannot be negative")
        if self.last_accessed_at is not None:
            _time(self.last_accessed_at, "last_accessed_at")
        if self.state is CacheEntryState.COLD:
            if self.observed_bytes != 0 or self.evictable:
                raise ValueError("cold cache entries contain no evictable bytes")
        elif self.last_accessed_at is None or self.observed_bytes <= 0:
            raise ValueError("resident cache entries require bytes and access time")
        if self.state is CacheEntryState.ACTIVE and self.evictable:
            raise ValueError("active cache entries cannot be evictable")


@dataclass(frozen=True, slots=True)
class CacheTelemetrySnapshot:
    snapshot_id: str
    sequence: int
    previous_snapshot_id: str | None
    observed_at: datetime
    entries: tuple[CacheTelemetryEntry, ...]
    current_host_state_complete: bool
    contract_version: str = CACHE_POLICY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != CACHE_POLICY_CONTRACT_VERSION:
            raise ValueError("unsupported cache policy contract_version")
        _text(self.snapshot_id, "snapshot_id")
        _time(self.observed_at, "observed_at")
        if self.sequence <= 0 or (self.sequence == 1) != (self.previous_snapshot_id is None):
            raise ValueError("cache snapshot sequence linkage is invalid")
        keys = tuple((item.tier, item.artifact_id) for item in self.entries)
        if not self.entries or len(keys) != len(set(keys)):
            raise ValueError("cache snapshot entries must be non-empty and unique by tier")


@dataclass(frozen=True, slots=True)
class CacheTierPressure:
    tier: CacheTier
    required_free_bytes: int

    def __post_init__(self) -> None:
        if self.required_free_bytes <= 0:
            raise ValueError("cache pressure must request positive bytes")


@dataclass(frozen=True, slots=True)
class CachePolicyRequest:
    request_id: str
    snapshot: CacheTelemetrySnapshot
    pressures: tuple[CacheTierPressure, ...]
    protected_artifact_ids: tuple[str, ...]
    policy_version: str = CACHE_POLICY_VERSION
    contract_version: str = CACHE_POLICY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != CACHE_POLICY_CONTRACT_VERSION:
            raise ValueError("unsupported cache policy contract_version")
        if self.policy_version != CACHE_POLICY_VERSION:
            raise ValueError("unsupported cache policy version")
        _text(self.request_id, "request_id")
        tiers = tuple(item.tier for item in self.pressures)
        if not tiers or len(tiers) != len(set(tiers)):
            raise ValueError("cache pressure tiers must be non-empty and unique")
        if len(self.protected_artifact_ids) != len(set(self.protected_artifact_ids)):
            raise ValueError("protected cache artifacts must be unique")


@dataclass(frozen=True, slots=True)
class CacheEvictionDecision:
    tier: CacheTier
    artifact_id: str
    rank: int
    reclaimable_bytes: int
    reason: str

    def __post_init__(self) -> None:
        _text(self.artifact_id, "artifact_id")
        _text(self.reason, "reason")
        if self.rank <= 0 or self.reclaimable_bytes <= 0:
            raise ValueError("cache eviction rank and bytes must be positive")


@dataclass(frozen=True, slots=True)
class CacheTierReclaim:
    tier: CacheTier
    required_free_bytes: int
    selected_bytes: int
    satisfied: bool

    def __post_init__(self) -> None:
        if self.required_free_bytes <= 0 or self.selected_bytes < 0:
            raise ValueError("cache reclaim counters are invalid")
        if self.satisfied != (self.selected_bytes >= self.required_free_bytes):
            raise ValueError("cache reclaim satisfaction is inconsistent")


@dataclass(frozen=True, slots=True)
class CachePolicyDecision:
    decision_id: str
    request_id: str
    evictions: tuple[CacheEvictionDecision, ...]
    reclaims: tuple[CacheTierReclaim, ...]
    all_pressures_satisfied: bool
    policy_version: str = CACHE_POLICY_VERSION
    contract_version: str = CACHE_POLICY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != CACHE_POLICY_CONTRACT_VERSION or self.policy_version != CACHE_POLICY_VERSION:
            raise ValueError("unsupported cache decision version")
        _text(self.decision_id, "decision_id")
        _text(self.request_id, "request_id")
        ranks = tuple(item.rank for item in self.evictions)
        if ranks and ranks != tuple(range(1, len(ranks) + 1)):
            raise ValueError("cache eviction ranks must be contiguous")
        if len({(item.tier, item.artifact_id) for item in self.evictions}) != len(self.evictions):
            raise ValueError("cache eviction selections must be unique")
        if self.all_pressures_satisfied != all(item.satisfied for item in self.reclaims):
            raise ValueError("cache decision satisfaction is inconsistent")


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _digest(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("cache source digest must be lowercase SHA-256")


def _time(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
