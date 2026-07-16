"""Port for local or remote model inference runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from fam_os.telemetry.contracts import InferenceMetrics


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class InferenceMessage:
    role: MessageRole
    content: str

    def __post_init__(self) -> None:
        if not self.content:
            raise ValueError("message content must not be empty")


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    model_ref: str
    messages: tuple[InferenceMessage, ...]
    context_tokens: int
    max_output_tokens: int
    keep_alive: str = "5m"
    json_output: bool = False
    temperature: float = 0.0
    seed: int | None = 42
    accelerator_layer_count: int | None = None
    main_accelerator_index: int | None = None

    def __post_init__(self) -> None:
        if not self.model_ref.strip():
            raise ValueError("model_ref must not be empty")
        if not self.messages:
            raise ValueError("at least one message is required")
        if self.context_tokens <= 0 or self.max_output_tokens <= 0:
            raise ValueError("token limits must be positive")
        if not self.keep_alive.strip():
            raise ValueError("keep_alive must not be empty")
        if self.temperature < 0:
            raise ValueError("temperature cannot be negative")
        if self.accelerator_layer_count is not None and self.accelerator_layer_count < 0:
            raise ValueError("accelerator_layer_count cannot be negative")
        if self.main_accelerator_index is not None:
            if self.main_accelerator_index < 0:
                raise ValueError("main_accelerator_index cannot be negative")
            if not self.accelerator_layer_count:
                raise ValueError("main accelerator requires positive accelerator layers")


@dataclass(frozen=True, slots=True)
class InferenceResponse:
    content: str
    metrics: InferenceMetrics


@dataclass(frozen=True, slots=True)
class LoadedModel:
    model_ref: str
    resident_bytes: int | None = None
    accelerator_bytes: int | None = None
    context_tokens: int | None = None

    def __post_init__(self) -> None:
        if not self.model_ref.strip():
            raise ValueError("model_ref must not be empty")
        values = (self.resident_bytes, self.accelerator_bytes, self.context_tokens)
        if any(value is not None and value < 0 for value in values):
            raise ValueError("loaded-model numeric values cannot be negative")


class InferenceRuntime(Protocol):
    """Boundary that Ollama and future runtimes must implement."""

    def chat(self, request: InferenceRequest) -> InferenceResponse: ...

    def unload(self, model_ref: str) -> None:
        """Return only after the runtime no longer reports the model as loaded."""
        ...

    def loaded_models(self) -> tuple[LoadedModel, ...]: ...
