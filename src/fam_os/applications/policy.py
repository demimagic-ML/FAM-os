"""Shared permission and action-policy vocabulary."""

from __future__ import annotations

from enum import StrEnum


class CapabilityKind(StrEnum):
    OBSERVATION = "observation"
    ACTION = "action"


class ApplicationAuthority(StrEnum):
    OBSERVE = "observe"
    PROPOSE = "propose"
    MODIFY = "modify"
    EXECUTE = "execute"


class ConfirmationPolicy(StrEnum):
    NOT_REQUIRED = "not_required"
    WHEN_REQUIRED = "when_required"
    ALWAYS = "always"


class Reversibility(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    REVERSIBLE = "reversible"
    COMPENSATABLE = "compensatable"
    IRREVERSIBLE = "irreversible"
