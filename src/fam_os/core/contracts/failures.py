"""Structured Core-facing failure and degradation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from re import fullmatch


FAILURE_CONTRACT_VERSION = "fam.failure/v1alpha1"


class FailureCategory(StrEnum):
    INVALID_REQUEST = "invalid_request"
    PERMISSION_DENIED = "permission_denied"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    INCOMPATIBLE = "incompatible"
    PROVIDER_FAILURE = "provider_failure"
    VERIFICATION_FAILED = "verification_failed"
    POSTCONDITION_FAILED = "postcondition_failed"
    INTERNAL = "internal"


class FailureComponent(StrEnum):
    CORE = "core"
    ROUTING = "routing"
    EXPERT = "expert"
    SCHEDULER = "scheduler"
    VERIFICATION = "verification"
    APPLICATION = "application"
    MEMORY = "memory"
    SUPERVISOR = "supervisor"
    REGISTRY = "registry"
    ADAPTER = "adapter"


class RetryDisposition(StrEnum):
    NEVER = "never"
    IMMEDIATE = "immediate"
    WITH_BACKOFF = "with_backoff"
    AFTER_USER_ACTION = "after_user_action"
    AFTER_RESOURCE_CHANGE = "after_resource_change"


class DegradationKind(StrEnum):
    FALLBACK_USED = "fallback_used"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    RESOURCE_CONSTRAINED = "resource_constrained"
    CONTEXT_REDUCED = "context_reduced"
    QUALITY_REDUCED = "quality_reduced"
    PARTIAL_RESULT = "partial_result"
    STALE_DATA = "stale_data"


class DegradationImpact(StrEnum):
    NONE = "none"
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DegradationDisposition(StrEnum):
    CONTINUE = "continue"
    REQUIRE_CONFIRMATION = "require_confirmation"
    WITHHOLD = "withhold"


def _require_text(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _require_code(code: str) -> str:
    normalized = _require_text("code", code).lower()
    if fullmatch(r"[a-z][a-z0-9_.-]*", normalized) is None or "." not in normalized:
        raise ValueError("code must be a namespaced lowercase identifier")
    return normalized


def _require_safe_message(message: str) -> str:
    normalized = _require_text("safe_message", message)
    if len(normalized) > 500 or any(character in normalized for character in "\r\n\t"):
        raise ValueError("safe_message must be one line and at most 500 characters")
    return normalized


def _normalize_ids(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(_require_text(name, value) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} values must be unique")
    return normalized


@dataclass(frozen=True, slots=True)
class FailureEnvelope:
    error_id: str
    category: FailureCategory
    code: str
    safe_message: str
    component: FailureComponent
    retry: RetryDisposition
    capability_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    contract_version: str = FAILURE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "error_id", _require_text("error_id", self.error_id))
        object.__setattr__(self, "code", _require_code(self.code))
        object.__setattr__(self, "safe_message", _require_safe_message(self.safe_message))
        object.__setattr__(self, "evidence_ids", _normalize_ids("evidence_id", self.evidence_ids))
        if self.contract_version != FAILURE_CONTRACT_VERSION:
            raise ValueError("unsupported failure contract_version")
        if self.capability_id is not None:
            object.__setattr__(
                self, "capability_id", _require_text("capability_id", self.capability_id)
            )
        if self.category is FailureCategory.PERMISSION_DENIED:
            allowed = {RetryDisposition.NEVER, RetryDisposition.AFTER_USER_ACTION}
            if self.retry not in allowed:
                raise ValueError("permission denial retry requires user action or never")
        if self.category is FailureCategory.CANCELLED and self.retry is not RetryDisposition.NEVER:
            raise ValueError("cancelled failures cannot be automatically retried")


@dataclass(frozen=True, slots=True)
class DegradationNotice:
    degradation_id: str
    kind: DegradationKind
    code: str
    safe_message: str
    component: FailureComponent
    impact: DegradationImpact
    disposition: DegradationDisposition
    original_capability_id: str | None = None
    replacement_capability_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    contract_version: str = FAILURE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "degradation_id", _require_text("degradation_id", self.degradation_id)
        )
        object.__setattr__(self, "code", _require_code(self.code))
        object.__setattr__(self, "safe_message", _require_safe_message(self.safe_message))
        object.__setattr__(self, "evidence_ids", _normalize_ids("evidence_id", self.evidence_ids))
        if self.contract_version != FAILURE_CONTRACT_VERSION:
            raise ValueError("unsupported degradation contract_version")
        self._normalize_capabilities()
        self._validate_kind()

    def _normalize_capabilities(self) -> None:
        for name in ("original_capability_id", "replacement_capability_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _require_text(name, value))

    def _validate_kind(self) -> None:
        if self.kind is DegradationKind.FALLBACK_USED:
            if self.original_capability_id is None or self.replacement_capability_id is None:
                raise ValueError("fallback degradation requires original and replacement capability")
            if self.original_capability_id == self.replacement_capability_id:
                raise ValueError("fallback capabilities must be different")
        if self.kind is DegradationKind.CAPABILITY_UNAVAILABLE:
            if self.original_capability_id is None:
                raise ValueError("unavailable degradation requires original capability")
        reduced = {DegradationKind.CONTEXT_REDUCED, DegradationKind.QUALITY_REDUCED}
        if self.kind in reduced and self.impact is DegradationImpact.NONE:
            raise ValueError("reduced context or quality must declare an impact")
