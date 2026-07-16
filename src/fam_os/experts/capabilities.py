"""Canonical Expert Fabric capability identifiers and matching policy."""

from __future__ import annotations

import re
from dataclasses import dataclass


EXPERT_CAPABILITY_NAMESPACE_VERSION = "fam.expert.capabilities/v1"

BUILT_IN_CAPABILITY_DOMAINS = frozenset(
    {
        "application",
        "code",
        "kernel",
        "language",
        "math",
        "retrieval",
        "routing",
        "safety",
        "speech",
        "verification",
        "vision",
    }
)

_SEGMENT = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_MAX_CAPABILITY_LENGTH = 128
_MAX_SEGMENTS = 8


@dataclass(frozen=True, slots=True)
class ExpertCapabilityId:
    """A parsed capability identity with no implied wildcard semantics."""

    value: str
    domain: str
    operation: str | None
    qualifiers: tuple[str, ...]
    publisher_id: str | None = None

    @property
    def is_vendor_extension(self) -> bool:
        return self.publisher_id is not None


def parse_expert_capability_id(
    value: str,
    *,
    publisher_id: str | None = None,
) -> ExpertCapabilityId:
    """Parse one built-in or publisher-owned capability identifier."""

    normalized = value.strip()
    parts = tuple(normalized.split("."))
    _require_valid_shape(value, normalized, parts)
    if parts[0] == "vendor":
        return _parse_vendor_capability(normalized, parts, publisher_id)
    if parts[0] not in BUILT_IN_CAPABILITY_DOMAINS:
        raise ValueError(f"unknown expert capability domain: {parts[0]}")
    operation = parts[1] if len(parts) > 1 else None
    return ExpertCapabilityId(normalized, parts[0], operation, parts[2:])


def require_expert_capabilities(
    values: tuple[str, ...],
    *,
    publisher_id: str | None = None,
) -> tuple[ExpertCapabilityId, ...]:
    """Validate a non-empty, unique set of capability identifiers."""

    if not values:
        raise ValueError("capabilities must not be empty")
    parsed = tuple(
        parse_expert_capability_id(value, publisher_id=publisher_id) for value in values
    )
    normalized = tuple(item.value for item in parsed)
    if len(set(normalized)) != len(normalized):
        raise ValueError("capabilities values must be unique")
    return parsed


def capability_satisfies(provided: str, required: str) -> bool:
    """Return exact capability equality; hierarchy never grants implicit scope."""

    return parse_expert_capability_id(provided).value == parse_expert_capability_id(required).value


def _require_valid_shape(value: str, normalized: str, parts: tuple[str, ...]) -> None:
    if value != normalized or not normalized:
        raise ValueError("expert capability IDs must be non-empty canonical strings")
    if len(normalized) > _MAX_CAPABILITY_LENGTH:
        raise ValueError("expert capability ID exceeds 128 characters")
    if len(parts) > _MAX_SEGMENTS:
        raise ValueError("expert capability ID exceeds eight segments")
    if any(not _SEGMENT.fullmatch(part) for part in parts):
        raise ValueError("expert capability ID segments must be lowercase canonical tokens")


def _parse_vendor_capability(
    value: str,
    parts: tuple[str, ...],
    expected_publisher_id: str | None,
) -> ExpertCapabilityId:
    if len(parts) < 4:
        raise ValueError("vendor capabilities require publisher, domain, and operation segments")
    publisher = parts[1]
    if expected_publisher_id is not None and publisher != expected_publisher_id:
        raise ValueError("vendor capability publisher does not match package publisher_id")
    return ExpertCapabilityId(value, parts[2], parts[3], parts[4:], publisher)
