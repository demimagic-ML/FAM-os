"""Evidence contracts for a non-releasing expert activation probe."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.core.ports.inference import LoadedModel
from fam_os.routing.contracts import RoutingResult
from fam_os.telemetry.contracts import InferenceMetrics


class ActivationProbeStatus(StrEnum):
    ACTIVATED = "activated"
    ROUTE_NOT_SUPPORTED = "route_not_supported"


@dataclass(frozen=True, slots=True)
class ActivationProbeOutcome:
    request_id: str
    status: ActivationProbeStatus
    routing: RoutingResult
    expert_id: str | None = None
    candidate: str | None = None
    metrics: InferenceMetrics | None = None
    evicted_expert_ids: tuple[str, ...] = ()
    loaded_after_routing: tuple[LoadedModel, ...] = ()
    loaded_after_placement: tuple[LoadedModel, ...] = ()
    loaded_after_expert: tuple[LoadedModel, ...] = ()

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must not be empty")
        if self.status is ActivationProbeStatus.ACTIVATED:
            if not self.expert_id or self.candidate is None or self.metrics is None:
                raise ValueError("activated probe requires expert evidence")
        elif self.expert_id is not None or self.candidate is not None or self.metrics is not None:
            raise ValueError("unsupported route cannot contain expert evidence")
