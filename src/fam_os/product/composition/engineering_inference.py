"""Composition of the bounded engineering-only chat provider."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.adapters.codex_subscription import (
    CodexSubscriptionRuntime, CodexSubscriptionSettings,
)
from fam_os.core.ports.inference import ChatInferenceRuntime


@dataclass(frozen=True, slots=True)
class EngineeringInference:
    runtime: ChatInferenceRuntime
    model_ref: str


def compose_engineering_inference(
    local_runtime: ChatInferenceRuntime, local_model_ref: str,
    codex_settings: CodexSubscriptionSettings | None,
    provided_runtime: ChatInferenceRuntime | None = None,
) -> EngineeringInference:
    if codex_settings is None:
        return EngineeringInference(
            provided_runtime or local_runtime, local_model_ref,
        )
    return EngineeringInference(
        provided_runtime or CodexSubscriptionRuntime(codex_settings),
        codex_settings.model_ref,
    )
