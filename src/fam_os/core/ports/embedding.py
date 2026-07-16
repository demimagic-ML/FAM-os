"""Provider-neutral text embedding runtime boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    model_ref: str
    inputs: tuple[str, ...]
    keep_alive: str = "5m"

    def __post_init__(self) -> None:
        if not self.model_ref.strip() or not self.inputs:
            raise ValueError("embedding model and inputs are required")
        if any(not value.strip() for value in self.inputs):
            raise ValueError("embedding inputs must not be empty")
        if not self.keep_alive.strip():
            raise ValueError("keep_alive must not be empty")


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    model_ref: str
    vectors: tuple[tuple[float, ...], ...]
    prompt_tokens: int
    wall_seconds: float

    def __post_init__(self) -> None:
        if not self.vectors or any(not vector for vector in self.vectors):
            raise ValueError("embedding response requires non-empty vectors")
        dimensions = {len(vector) for vector in self.vectors}
        if len(dimensions) != 1:
            raise ValueError("embedding vectors must share one dimension")
        if self.prompt_tokens < 0 or self.wall_seconds < 0:
            raise ValueError("embedding metrics cannot be negative")


class EmbeddingRuntime(Protocol):
    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse: ...
