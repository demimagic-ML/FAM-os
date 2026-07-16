"""Latency-aware local-versus-trusted-remote scheduling."""

from dataclasses import dataclass

FABRIC_SCHEDULING_CONTRACT_VERSION = "fam.fabric.scheduling/v1alpha1"


@dataclass(frozen=True, slots=True)
class FabricRouteCandidate:
    device_id: str
    expert_id: str
    local: bool
    inference_milliseconds: float
    network_round_trip_milliseconds: float
    privacy_allowed: bool
    trusted: bool

    @property
    def completion_milliseconds(self):
        return self.inference_milliseconds + (0 if self.local else self.network_round_trip_milliseconds)


@dataclass(frozen=True, slots=True)
class FabricRouteDecision:
    selected_device_id: str
    selected_expert_id: str
    predicted_completion_milliseconds: float
    considered_device_ids: tuple[str, ...]
    contract_version: str = FABRIC_SCHEDULING_CONTRACT_VERSION


class LatencyAwareFabricScheduler:
    def decide(self, candidates):
        values = tuple(item for item in candidates if item.trusted and item.privacy_allowed)
        if not values:
            raise ValueError("no trusted privacy-allowed fabric route")
        selected = min(values, key=lambda item: (item.completion_milliseconds, not item.local,
                                                  item.device_id, item.expert_id))
        return FabricRouteDecision(
            selected.device_id, selected.expert_id, selected.completion_milliseconds,
            tuple(item.device_id for item in values),
        )
