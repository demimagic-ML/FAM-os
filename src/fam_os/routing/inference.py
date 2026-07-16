"""Model-backed routing policy over the provider-neutral inference port."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.core.ports.inference import InferenceRequest, InferenceRuntime
from fam_os.routing.contracts import RoutingRequest, RoutingResult
from fam_os.routing.parsing import parse_route_decision
from fam_os.routing.prompts import routing_messages


@dataclass(frozen=True, slots=True)
class ModelRouterSettings:
    model_ref: str
    context_tokens: int = 2_048
    max_output_tokens: int = 100
    keep_alive: str = "5m"
    temperature: float = 0.0
    seed: int | None = 42

    def __post_init__(self) -> None:
        if not self.model_ref.strip():
            raise ValueError("model_ref must not be empty")
        if self.context_tokens <= 0 or self.max_output_tokens <= 0:
            raise ValueError("token limits must be positive")
        if not self.keep_alive.strip():
            raise ValueError("keep_alive must not be empty")
        if self.temperature < 0:
            raise ValueError("temperature cannot be negative")


class ModelTaskRouter:
    def __init__(self, runtime: InferenceRuntime, settings: ModelRouterSettings) -> None:
        self._runtime = runtime
        self._settings = settings

    def route(self, request: RoutingRequest) -> RoutingResult:
        response = self._runtime.chat(build_model_routing_request(self._settings, request))
        decision = parse_route_decision(response.content, request)
        return RoutingResult(decision, response.metrics)


def build_model_routing_request(
    settings: ModelRouterSettings,
    request: RoutingRequest,
) -> InferenceRequest:
    return InferenceRequest(
        model_ref=settings.model_ref,
        messages=routing_messages(request.prompt),
        context_tokens=settings.context_tokens,
        max_output_tokens=settings.max_output_tokens,
        keep_alive=settings.keep_alive,
        json_output=True,
        temperature=settings.temperature,
        seed=settings.seed,
    )
