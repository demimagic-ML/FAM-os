"""Advisory-only production boundary for verified local adaptation."""

from __future__ import annotations

from typing import Protocol

from fam_os.core.ports.inference import InferenceMessage
from fam_os.core.production.contracts import ModelIntent


class LiveAdaptationPort(Protocol):
    def preferred_model_refs(self, intent: ModelIntent) -> tuple[str, ...]: ...

    def context_tokens(
        self,
        request_id: str,
        intent: ModelIntent,
        model_ref: str,
        messages: tuple[InferenceMessage, ...],
        max_output_tokens: int,
        default_context_tokens: int,
    ) -> int: ...

    def inference_completed(
        self, observation_id: str, request_id: str,
        intent: ModelIntent, model_ref: str, metrics,
    ) -> None: ...
