"""Metrics emitted by inference-runtime adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InferenceMetrics:
    model_ref: str
    wall_seconds: float
    load_seconds: float
    prompt_tokens: int
    output_tokens: int
    generation_tokens_per_second: float | None = None

    def __post_init__(self) -> None:
        if not self.model_ref.strip():
            raise ValueError("model_ref must not be empty")
        numeric = (self.wall_seconds, self.load_seconds, self.prompt_tokens, self.output_tokens)
        if any(value < 0 for value in numeric):
            raise ValueError("metric values cannot be negative")
        if self.generation_tokens_per_second is not None and self.generation_tokens_per_second < 0:
            raise ValueError("generation rate cannot be negative")

