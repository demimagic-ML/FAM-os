"""Auditable configuration composition decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ConfigurationLayer(StrEnum):
    DEFAULTS = "defaults"
    DISCOVERY = "discovery"
    VALIDATION_PROFILE = "validation_profile"
    USER_POLICY = "user_policy"
    SESSION_OVERRIDE = "session_override"


class ConfigurationDecisionKind(StrEnum):
    SELECTED = "selected"
    OVERRIDDEN = "overridden"
    RESTRICTED = "restricted"
    CLAMPED = "clamped"
    IGNORED = "ignored"


@dataclass(frozen=True, slots=True)
class ConfigurationDecision:
    layer: ConfigurationLayer
    source_id: str
    setting: str
    requested_value: str
    effective_value: str
    kind: ConfigurationDecisionKind
    reason_code: str

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "setting",
            "requested_value",
            "effective_value",
            "reason_code",
        ):
            value = getattr(self, name).strip()
            if not value or any(character in value for character in "\r\n\t"):
                raise ValueError(f"configuration decision {name} must be one non-empty line")
