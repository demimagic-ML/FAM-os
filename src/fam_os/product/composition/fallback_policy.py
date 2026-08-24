"""Strict owner policy for privacy-sensitive desktop fallback mechanisms."""

from __future__ import annotations

from dataclasses import dataclass, field

from fam_os.adapters.linux.accessibility.bridge import DEFAULT_ALLOWED_ACTIONS
from fam_os.adapters.linux.screen_input.policy import DEFAULT_KEYS
from fam_os.applications import ScreenInputKind, ScreenTarget
from fam_os.applications.identifiers import require_identifier


FALLBACK_CONFIG_VERSION = "fam.product.fallbacks/v1alpha1"
_ACCESSIBILITY_FIELDS = frozenset({
    "enabled", "privacy_acknowledged", "include_text", "actions_enabled",
    "allowed_actions", "targets",
})
_SCREEN_FIELDS = frozenset({
    "enabled", "privacy_acknowledged", "actions_enabled", "allowed_kinds",
    "allowed_keys", "targets",
})


@dataclass(frozen=True, slots=True)
class AccessibilityTargetPolicy:
    connector_id: str
    instance_id: str
    process_id: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "connector_id", require_identifier(self.connector_id, "connector_id"),
        )
        object.__setattr__(
            self, "instance_id", require_identifier(self.instance_id, "instance_id"),
        )
        if isinstance(self.process_id, bool) or self.process_id <= 0:
            raise ValueError("accessibility process_id must be a positive integer")


@dataclass(frozen=True, slots=True)
class AccessibilityFallbackPolicy:
    enabled: bool = False
    privacy_acknowledged: bool = False
    include_text: bool = False
    actions_enabled: bool = False
    allowed_actions: tuple[str, ...] = DEFAULT_ALLOWED_ACTIONS
    targets: tuple[AccessibilityTargetPolicy, ...] = ()

    def __post_init__(self) -> None:
        _require_explicit_privacy(self.enabled, self.privacy_acknowledged)
        if self.actions_enabled and not self.enabled:
            raise ValueError("accessibility actions require the fallback to be enabled")
        actions = _unique_text(self.allowed_actions, "allowed_actions", 32)
        if self.actions_enabled and not actions:
            raise ValueError("enabled accessibility actions require an allowlist")
        if self.enabled and not self.targets:
            raise ValueError("enabled accessibility fallback requires exact targets")
        _require_unique_targets(
            tuple(item.instance_id for item in self.targets),
            tuple(item.connector_id for item in self.targets),
        )
        object.__setattr__(self, "allowed_actions", actions)


@dataclass(frozen=True, slots=True)
class ScreenTargetPolicy:
    connector_id: str
    instance_id: str
    target: ScreenTarget

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "connector_id", require_identifier(self.connector_id, "connector_id"),
        )
        object.__setattr__(
            self, "instance_id", require_identifier(self.instance_id, "instance_id"),
        )


@dataclass(frozen=True, slots=True)
class ScreenFallbackPolicy:
    enabled: bool = False
    privacy_acknowledged: bool = False
    actions_enabled: bool = False
    allowed_kinds: tuple[ScreenInputKind, ...] = (
        ScreenInputKind.POINTER_CLICK, ScreenInputKind.KEY_CHORD,
    )
    allowed_keys: tuple[str, ...] = DEFAULT_KEYS
    targets: tuple[ScreenTargetPolicy, ...] = ()

    def __post_init__(self) -> None:
        _require_explicit_privacy(self.enabled, self.privacy_acknowledged)
        if self.actions_enabled and not self.enabled:
            raise ValueError("screen input requires the fallback to be enabled")
        if not self.allowed_kinds or len(set(self.allowed_kinds)) != len(self.allowed_kinds):
            raise ValueError("screen input kinds must be a non-empty unique allowlist")
        keys = _unique_text(self.allowed_keys, "allowed_keys", 128)
        if ScreenInputKind.KEY_CHORD in self.allowed_kinds and not keys:
            raise ValueError("key-chord input requires an allowed key list")
        if self.enabled and not self.targets:
            raise ValueError("enabled screen fallback requires exact targets")
        _require_unique_targets(
            tuple(item.instance_id for item in self.targets),
            tuple(item.connector_id for item in self.targets),
        )
        object.__setattr__(self, "allowed_keys", keys)


@dataclass(frozen=True, slots=True)
class ProductFallbackPolicy:
    accessibility: AccessibilityFallbackPolicy = field(
        default_factory=AccessibilityFallbackPolicy,
    )
    screen_input: ScreenFallbackPolicy = field(default_factory=ScreenFallbackPolicy)

    def __post_init__(self) -> None:
        connectors = tuple(
            item.connector_id for item in self.accessibility.targets
        ) + tuple(item.connector_id for item in self.screen_input.targets)
        instances = tuple(
            item.instance_id for item in self.accessibility.targets
        ) + tuple(item.instance_id for item in self.screen_input.targets)
        if len(set(connectors)) != len(connectors):
            raise ValueError("fallback connector IDs must be globally unique")
        if len(set(instances)) != len(instances):
            raise ValueError("fallback instance IDs must be globally unique")


def parse_fallback_policy(document: object) -> ProductFallbackPolicy:
    root = _exact_object(
        document, {"contract_version", "accessibility", "screen_input"}, "fallback",
    )
    if root["contract_version"] != FALLBACK_CONFIG_VERSION:
        raise ValueError("fallback configuration version is unsupported")
    return ProductFallbackPolicy(
        _accessibility(root["accessibility"]), _screen(root["screen_input"]),
    )


def _accessibility(value: object) -> AccessibilityFallbackPolicy:
    item = _exact_object(value, _ACCESSIBILITY_FIELDS, "accessibility")
    targets = _target_list(item["targets"], "accessibility")
    return AccessibilityFallbackPolicy(
        _boolean(item, "enabled"), _boolean(item, "privacy_acknowledged"),
        _boolean(item, "include_text"), _boolean(item, "actions_enabled"),
        _string_list(item["allowed_actions"], "allowed_actions", 32),
        tuple(_accessibility_target(target) for target in targets),
    )


def _screen(value: object) -> ScreenFallbackPolicy:
    item = _exact_object(value, _SCREEN_FIELDS, "screen_input")
    targets = _target_list(item["targets"], "screen_input")
    kinds = tuple(
        ScreenInputKind(value)
        for value in _string_list(item["allowed_kinds"], "allowed_kinds", 2)
    )
    return ScreenFallbackPolicy(
        _boolean(item, "enabled"), _boolean(item, "privacy_acknowledged"),
        _boolean(item, "actions_enabled"), kinds,
        _string_list(item["allowed_keys"], "allowed_keys", 128),
        tuple(_screen_target(target) for target in targets),
    )


def _accessibility_target(value: object) -> AccessibilityTargetPolicy:
    item = _exact_object(
        value, {"connector_id", "instance_id", "process_id"},
        "accessibility target",
    )
    return AccessibilityTargetPolicy(
        item["connector_id"], item["instance_id"], _positive_int(item, "process_id"),
    )


def _screen_target(value: object) -> ScreenTargetPolicy:
    item = _exact_object(
        value, {
            "connector_id", "instance_id", "application_id", "process_id", "window_id",
        },
        "screen target",
    )
    return ScreenTargetPolicy(
        item["connector_id"], item["instance_id"], ScreenTarget(
            item["application_id"], _positive_int(item, "process_id"), item["window_id"],
        ),
    )


def _exact_object(value: object, fields: set[str] | frozenset[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{name} configuration fields are invalid")
    return value


def _target_list(value: object, name: str) -> list:
    if not isinstance(value, list) or len(value) > 32:
        raise ValueError(f"{name} targets must be an array with at most 32 entries")
    return value


def _string_list(value: object, name: str, maximum: int) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{name} must be a bounded string array")
    return _unique_text(tuple(value), name, maximum)


def _unique_text(values: tuple, name: str, maximum: int) -> tuple[str, ...]:
    if len(values) > maximum or any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError(f"{name} must contain non-empty strings")
    normalized = tuple(item.strip() for item in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} values must be unique")
    return normalized


def _boolean(value: dict, name: str) -> bool:
    item = value[name]
    if not isinstance(item, bool):
        raise ValueError(f"{name} must be boolean")
    return item


def _positive_int(value: dict, name: str) -> int:
    item = value[name]
    if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return item


def _require_explicit_privacy(enabled: bool, acknowledged: bool) -> None:
    if enabled and not acknowledged:
        raise PermissionError("enabled fallback requires explicit privacy acknowledgement")


def _require_unique_targets(
    instance_ids: tuple[str, ...], connector_ids: tuple[str, ...],
) -> None:
    if len(set(instance_ids)) != len(instance_ids):
        raise ValueError("fallback target instance IDs must be unique")
    if len(set(connector_ids)) != len(connector_ids):
        raise ValueError("fallback target connector IDs must be unique")
