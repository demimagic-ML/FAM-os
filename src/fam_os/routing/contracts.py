"""Typed routing input and output independent of a router implementation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re

from fam_os.telemetry.contracts import InferenceMetrics


ROUTING_CONTRACT_VERSION = "fam.routing/v1alpha1"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_MAX_PROMPT_CHARACTERS = 131_072


class RouteName(StrEnum):
    KERNEL = "kernel"
    CODE = "code"
    MATH = "math"
    RETRIEVAL = "retrieval"


@dataclass(frozen=True, slots=True)
class RouteDecision:
    route: RouteName
    confidence: float
    reason: str
    required_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if (
            not self.reason.strip() or len(self.reason) > 500
            or any(character in self.reason for character in "\r\n\t")
        ):
            raise ValueError("reason must not be empty")
        capabilities = tuple(capability.strip() for capability in self.required_capabilities)
        _require_capabilities(capabilities)
        object.__setattr__(self, "required_capabilities", capabilities)


@dataclass(frozen=True, slots=True)
class RoutingRequest:
    request_id: str
    prompt: str
    required_capabilities: tuple[str, ...] = ()
    contract_version: str = ROUTING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.request_id):
            raise ValueError("request_id is invalid")
        if (
            not self.prompt.strip() or "\0" in self.prompt
            or len(self.prompt) > _MAX_PROMPT_CHARACTERS
        ):
            raise ValueError("prompt must not be empty")
        if self.contract_version != ROUTING_CONTRACT_VERSION:
            raise ValueError("unsupported routing contract_version")
        capabilities = tuple(capability.strip() for capability in self.required_capabilities)
        _require_capabilities(capabilities)
        object.__setattr__(self, "required_capabilities", capabilities)


@dataclass(frozen=True, slots=True)
class RoutingResult:
    decision: RouteDecision
    metrics: InferenceMetrics | None = None
    contract_version: str = ROUTING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != ROUTING_CONTRACT_VERSION:
            raise ValueError("unsupported routing contract_version")


def _require_capabilities(capabilities: tuple[str, ...]) -> None:
    if len(capabilities) > 64:
        raise ValueError("too many required capabilities")
    if any(not _IDENTIFIER.fullmatch(value) for value in capabilities):
        raise ValueError("required capability is invalid")
    if len(set(capabilities)) != len(capabilities):
        raise ValueError("required capabilities must be unique")
