"""Versioned defaults, trusted profiles, and restriction-layer contracts."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime

from fam_os.scheduler.resources import (
    COMPAT_CPU_16GB_PROFILE_ID,
    ValidationProfileRef,
)


CONFIGURATION_CONTRACT_VERSION = "fam.configuration/v1alpha1"


def _fraction(name: str, value: float, *, zero_allowed: bool = False) -> None:
    lower = 0.0 if zero_allowed else 0.0
    if value < lower or value > 1.0 or (not zero_allowed and value == 0.0):
        raise ValueError(f"{name} must be within the allowed fraction range")


def _non_negative(name: str, values: tuple[int | float | None, ...]) -> None:
    if any(value is not None and value < 0 for value in values):
        raise ValueError(f"{name} values cannot be negative")


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    cpu_quota_fraction: float
    reserved_logical_cpu_count: int
    memory_limit_fraction: float
    memory_headroom_bytes: int
    max_swap_bytes: int
    accelerator_allowed: bool
    accelerator_memory_fraction: float
    accelerator_reserved_memory_bytes: int
    storage_cache_fraction: float
    storage_reserved_free_bytes: int
    max_cpu_cores: float | None = None
    max_memory_bytes: int | None = None
    max_accelerator_memory_bytes: int | None = None
    max_storage_cache_bytes: int | None = None
    storage_read_limit_bytes_per_second: int | None = None
    storage_write_limit_bytes_per_second: int | None = None

    def __post_init__(self) -> None:
        _fraction("cpu_quota_fraction", self.cpu_quota_fraction)
        _fraction("memory_limit_fraction", self.memory_limit_fraction)
        _fraction("accelerator_memory_fraction", self.accelerator_memory_fraction, zero_allowed=True)
        _fraction("storage_cache_fraction", self.storage_cache_fraction, zero_allowed=True)
        _non_negative("resource policy", tuple(getattr(self, field.name) for field in fields(self) if field.name not in {"accelerator_allowed"}))
        if self.max_cpu_cores == 0 or self.max_memory_bytes == 0:
            raise ValueError("positive resource maxima cannot be zero")
        if self.accelerator_allowed and self.accelerator_memory_fraction == 0:
            raise ValueError("allowed acceleration requires a positive memory fraction")
        for rate in (
            self.storage_read_limit_bytes_per_second,
            self.storage_write_limit_bytes_per_second,
        ):
            if rate == 0:
                raise ValueError("storage rate limits must be positive when provided")


@dataclass(frozen=True, slots=True)
class ResourceRestriction:
    max_cpu_cores: float | None = None
    max_memory_bytes: int | None = None
    minimum_memory_headroom_bytes: int | None = None
    max_swap_bytes: int | None = None
    accelerator_allowed: bool | None = None
    max_accelerator_memory_bytes: int | None = None
    minimum_accelerator_reserve_bytes: int | None = None
    max_storage_cache_bytes: int | None = None
    minimum_storage_reserve_bytes: int | None = None
    max_storage_read_bytes_per_second: int | None = None
    max_storage_write_bytes_per_second: int | None = None

    def __post_init__(self) -> None:
        values = tuple(getattr(self, field.name) for field in fields(self))
        if all(value is None for value in values):
            raise ValueError("resource restriction must constrain at least one setting")
        numeric = tuple(value for value in values if type(value) is not bool)
        _non_negative("resource restriction", numeric)
        for name in ("max_cpu_cores", "max_memory_bytes"):
            if getattr(self, name) == 0:
                raise ValueError(f"{name} must be positive when provided")


@dataclass(frozen=True, slots=True)
class SchedulerDefaults:
    configuration_id: str
    default_profile: ValidationProfileRef
    policy: ResourcePolicy
    contract_version: str = CONFIGURATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _validate_root(self.configuration_id, self.contract_version)
        _validate_profile_acceleration(self.default_profile, self.policy)


@dataclass(frozen=True, slots=True)
class ValidationProfileConfiguration:
    configuration_id: str
    profile: ValidationProfileRef
    policy: ResourcePolicy
    contract_version: str = CONFIGURATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _validate_root(self.configuration_id, self.contract_version)
        _validate_profile_acceleration(self.profile, self.policy)


@dataclass(frozen=True, slots=True)
class UserResourcePolicy:
    policy_id: str
    restriction: ResourceRestriction
    contract_version: str = CONFIGURATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _validate_root(self.policy_id, self.contract_version)


@dataclass(frozen=True, slots=True)
class SessionResourceOverride:
    override_id: str
    session_id: str
    issued_at: datetime
    restriction: ResourceRestriction
    expires_at: datetime | None = None
    contract_version: str = CONFIGURATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _validate_root(self.override_id, self.contract_version)
        if not self.session_id.strip():
            raise ValueError("session_id must not be empty")
        if self.issued_at.tzinfo is None:
            raise ValueError("issued_at must be timezone-aware")
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None or self.expires_at <= self.issued_at:
                raise ValueError("expires_at must be aware and follow issued_at")

    def active_at(self, instant: datetime) -> bool:
        if instant.tzinfo is None:
            raise ValueError("instant must be timezone-aware")
        return instant >= self.issued_at and (
            self.expires_at is None or instant < self.expires_at
        )


def _validate_root(identifier: str, contract_version: str) -> None:
    if not identifier.strip():
        raise ValueError("configuration identifier must not be empty")
    if contract_version != CONFIGURATION_CONTRACT_VERSION:
        raise ValueError("unsupported configuration contract_version")


def _validate_profile_acceleration(
    profile: ValidationProfileRef, policy: ResourcePolicy
) -> None:
    if profile.profile_id == COMPAT_CPU_16GB_PROFILE_ID and policy.accelerator_allowed:
        raise ValueError("compat-cpu-16gb configuration cannot allow acceleration")
