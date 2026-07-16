"""Route and activate one expert while retaining provider-neutral measurements."""

from __future__ import annotations

from fam_os.core.activation.contracts import ActivationProbeOutcome, ActivationProbeStatus
from fam_os.core.activation.prompts import activation_messages
from fam_os.core.contracts.request import TaskRequest
from fam_os.core.execution.placement import PlacementExecutor
from fam_os.core.execution.policy import GenerationSettings
from fam_os.core.ports.inference import InferenceRequest, InferenceRuntime
from fam_os.experts.contracts import ExpertDescriptor
from fam_os.experts.ports import ExpertCatalog
from fam_os.routing.contracts import RouteName, RoutingRequest
from fam_os.routing.ports import TaskRouter
from fam_os.scheduler.contracts import PlacementPlan


class ExpertActivationProbe:
    def __init__(
        self,
        runtime: InferenceRuntime,
        router: TaskRouter,
        catalog: ExpertCatalog,
        placement: PlacementExecutor,
    ) -> None:
        self._runtime = runtime
        self._router = router
        self._catalog = catalog
        self._placement = placement

    def execute(
        self,
        request: TaskRequest,
        expert_id: str,
        settings: GenerationSettings,
    ) -> ActivationProbeOutcome:
        routing = self._router.route(
            RoutingRequest(request.request_id, request.prompt, request.required_capabilities)
        )
        loaded_after_routing = self._runtime.loaded_models()
        if routing.decision.route is not RouteName.CODE:
            return ActivationProbeOutcome(
                request.request_id,
                ActivationProbeStatus.ROUTE_NOT_SUPPORTED,
                routing,
                loaded_after_routing=loaded_after_routing,
            )
        expert = self._require_expert(expert_id)
        prepared = self._placement.prepare(expert)
        loaded_after_placement = self._runtime.loaded_models()
        response = self._runtime.chat(
            self._request(request, expert, prepared.plan, settings)
        )
        return ActivationProbeOutcome(
            request_id=request.request_id,
            status=ActivationProbeStatus.ACTIVATED,
            routing=routing,
            expert_id=expert.expert_id,
            candidate=response.content,
            metrics=response.metrics,
            evicted_expert_ids=prepared.evicted_expert_ids,
            loaded_after_routing=loaded_after_routing,
            loaded_after_placement=loaded_after_placement,
            loaded_after_expert=self._runtime.loaded_models(),
        )

    def _require_expert(self, expert_id: str) -> ExpertDescriptor:
        expert = self._catalog.get(expert_id)
        if expert is None:
            raise ValueError(f"unknown expert: {expert_id}")
        return expert

    @staticmethod
    def _request(
        request: TaskRequest,
        expert: ExpertDescriptor,
        placement: PlacementPlan,
        settings: GenerationSettings,
    ) -> InferenceRequest:
        context_tokens = placement.budget.context_tokens
        if context_tokens > expert.max_context_tokens:
            raise ValueError("placement context exceeds expert maximum")
        return InferenceRequest(
            model_ref=expert.model_ref,
            messages=activation_messages(request.prompt),
            context_tokens=context_tokens,
            max_output_tokens=settings.max_output_tokens,
            keep_alive=settings.keep_alive,
            temperature=settings.temperature,
            seed=settings.seed,
        )
