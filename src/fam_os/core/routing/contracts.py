"""Core lifecycle evidence binding an admitted request to one valid route."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.core.admission import AdmittedTaskRequest
from fam_os.core.contracts import FailureEnvelope
from fam_os.routing.contracts import RoutingResult


@dataclass(frozen=True, slots=True)
class RoutedTaskRequest:
    admitted: AdmittedTaskRequest
    routing: RoutingResult

    def __post_init__(self) -> None:
        expected = self.admitted.permission.authorized_capabilities
        if self.routing.decision.required_capabilities != expected:
            raise ValueError("route must preserve exact effective capabilities")

    @property
    def request_id(self) -> str:
        return self.admitted.request.request_id


@dataclass(frozen=True, slots=True)
class CoreRoutingOutcome:
    request_id: str
    routed: RoutedTaskRequest | None = None
    failure: FailureEnvelope | None = None

    def __post_init__(self) -> None:
        if (self.routed is None) == (self.failure is None):
            raise ValueError("routing outcome requires exactly one result")
        if self.routed is not None and self.routed.request_id != self.request_id:
            raise ValueError("routed request identity does not match outcome")

    @property
    def succeeded(self) -> bool:
        return self.routed is not None
