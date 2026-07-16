"""One inference-and-verification attempt with no retry policy."""

from __future__ import annotations

from fam_os.core.execution.contracts import AttemptKind, ExecutionAttempt
from fam_os.core.execution.policy import GenerationSettings
from fam_os.core.ports.inference import InferenceMessage, InferenceRequest, InferenceRuntime
from fam_os.experts.contracts import ExpertDescriptor
from fam_os.scheduler.contracts import PlacementPlan
from fam_os.verification.contracts import VerificationRequest
from fam_os.verification.ports import Verifier


class CandidateGenerationError(RuntimeError):
    """Raised when inference returns no candidate that can be verified."""


class AttemptExecutor:
    def __init__(self, runtime: InferenceRuntime, verifier: Verifier) -> None:
        self._runtime = runtime
        self._verifier = verifier

    def execute(
        self,
        attempt_id: str,
        kind: AttemptKind,
        expert: ExpertDescriptor,
        placement: PlacementPlan,
        messages: tuple[InferenceMessage, ...],
        settings: GenerationSettings,
    ) -> ExecutionAttempt:
        response = self._runtime.chat(
            self._request(expert, placement, messages, settings)
        )
        if not response.content.strip():
            raise CandidateGenerationError("inference produced an empty candidate")
        verification = self._verifier.verify(
            VerificationRequest(attempt_id, response.content)
        )
        return ExecutionAttempt(
            attempt_id=attempt_id,
            kind=kind,
            expert_id=expert.expert_id,
            model_ref=expert.model_ref,
            candidate=response.content,
            metrics=response.metrics,
            verification=verification,
        )

    @staticmethod
    def _request(
        expert: ExpertDescriptor,
        placement: PlacementPlan,
        messages: tuple[InferenceMessage, ...],
        settings: GenerationSettings,
    ) -> InferenceRequest:
        context_tokens = placement.budget.context_tokens
        if placement.expert_id != expert.expert_id:
            raise ValueError("placement plan targets a different expert")
        if context_tokens > expert.max_context_tokens:
            raise ValueError("placement context exceeds expert maximum")
        return InferenceRequest(
            model_ref=expert.model_ref,
            messages=messages,
            context_tokens=context_tokens,
            max_output_tokens=settings.max_output_tokens,
            keep_alive=settings.keep_alive,
            temperature=settings.temperature,
            seed=settings.seed,
        )
