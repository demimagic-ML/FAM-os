"""Small fakes shared by verified-execution unit tests."""

from __future__ import annotations

from fam_os.core.ports.inference import (
    InferenceRequest,
    InferenceResponse,
    LoadedModel,
)
from fam_os.experts import ExpertDescriptor, ExpertTier
from fam_os.routing import RouteDecision, RouteName, RoutingRequest, RoutingResult
from fam_os.scheduler import PlacementPlan, ResourceBudget
from fam_os.telemetry.contracts import InferenceMetrics
from fam_os.verification import (
    VerificationEvidence,
    VerificationReport,
    VerificationRequest,
    VerificationStatus,
)


def expert(
    expert_id: str,
    model_ref: str,
    tier: ExpertTier,
) -> ExpertDescriptor:
    return ExpertDescriptor(
        expert_id=expert_id,
        model_ref=model_ref,
        tier=tier,
        capabilities=("code",),
        max_context_tokens=4_096,
        estimated_resident_bytes=1_000_000,
        verifier_ids=("fake-verifier",),
    )


def plan(
    expert_id: str,
    evictions: tuple[str, ...] = (),
    context_tokens: int = 2_048,
) -> PlacementPlan:
    return PlacementPlan(
        expert_id,
        ResourceBudget(4_000_000_000, 0, context_tokens),
        evictions,
    )


class FakeRuntime:
    def __init__(self, contents: list[str]) -> None:
        self.contents = list(contents)
        self.requests: list[InferenceRequest] = []
        self.unloaded: list[str] = []

    def chat(self, request: InferenceRequest) -> InferenceResponse:
        self.requests.append(request)
        content = self.contents.pop(0)
        metrics = InferenceMetrics(request.model_ref, 0.1, 0.0, 10, 5, 50.0)
        return InferenceResponse(content, metrics)

    def unload(self, model_ref: str) -> None:
        self.unloaded.append(model_ref)

    def loaded_models(self) -> tuple[LoadedModel, ...]:
        return ()


class FakeVerifier:
    def __init__(self, statuses: list[VerificationStatus]) -> None:
        self.statuses = list(statuses)
        self.requests: list[VerificationRequest] = []

    def verify(self, request: VerificationRequest) -> VerificationReport:
        self.requests.append(request)
        status = self.statuses.pop(0)
        reason = "trusted tests passed" if status is VerificationStatus.PASSED else "tests failed"
        if status is VerificationStatus.ERROR:
            reason = "verifier unavailable"
        return VerificationReport(
            verification_id=request.verification_id,
            verifier_id="fake-verifier",
            status=status,
            stage="tests",
            reason=reason,
            wall_seconds=0.01,
            evidence=VerificationEvidence(stderr="assertion failed"),
        )


class FakeRouter:
    def __init__(self, route: RouteName = RouteName.CODE) -> None:
        self.route_name = route
        self.requests: list[RoutingRequest] = []

    def route(self, request: RoutingRequest) -> RoutingResult:
        self.requests.append(request)
        return RoutingResult(RouteDecision(self.route_name, 1.0, "fake route"))


class FakeCatalog:
    def __init__(self, experts: tuple[ExpertDescriptor, ...]) -> None:
        self.experts = {item.expert_id: item for item in experts}

    def get(self, expert_id: str) -> ExpertDescriptor | None:
        return self.experts.get(expert_id)


class FakePlanner:
    def __init__(self, plans: tuple[PlacementPlan, ...]) -> None:
        self.plans = {item.expert_id: item for item in plans}
        self.requested: list[str] = []

    def plan(self, selected: ExpertDescriptor) -> PlacementPlan:
        self.requested.append(selected.expert_id)
        return self.plans[selected.expert_id]
