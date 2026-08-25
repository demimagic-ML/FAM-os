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
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class InferenceTool:
    name: str
    description: str
    parameters: dict[str, object]

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.description.strip():
            raise ValueError("inference tool name and description are required")
        if self.parameters.get("type") != "object":
            raise ValueError("inference tool parameters must be an object schema")


@dataclass(frozen=True, slots=True)
class InferenceToolCall:
    call_id: str
    name: str
    arguments: dict[str, object]

    def __post_init__(self) -> None:
        if not self.call_id.strip() or not self.name.strip():
            raise ValueError("inference tool call identity is required")
        if not isinstance(self.arguments, dict):
            raise ValueError("inference tool call arguments must be an object")


@dataclass(frozen=True, slots=True)
class InferenceMessage:
    role: MessageRole
    content: str
    images: tuple[bytes, ...] = ()
    tool_calls: tuple[InferenceToolCall, ...] = ()
    tool_call_id: str | None = None
    tool_name: str | None = None
    reasoning_content: str | None = None

    def __post_init__(self) -> None:
        if not self.content and not self.tool_calls:
            raise ValueError("message content must not be empty")
        if len(self.images) > 8 or any(not item for item in self.images):
            raise ValueError("inference message images are invalid")
        if sum(len(item) for item in self.images) > 25 * 1024 * 1024:
            raise ValueError("inference message images exceed their byte bound")
        if self.role is MessageRole.TOOL:
            if not self.tool_call_id or not self.tool_name or self.tool_calls:
                raise ValueError("tool message requires one call identity and name")
        elif self.tool_call_id is not None or self.tool_name is not None:
            raise ValueError("only tool messages may carry tool result identity")
        if self.tool_calls and self.role is not MessageRole.ASSISTANT:
            raise ValueError("only assistant messages may carry tool calls")
        if self.reasoning_content is not None and self.role is not MessageRole.ASSISTANT:
            raise ValueError("only assistant messages may carry preserved reasoning")


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
    tools: tuple[InferenceTool, ...] = ()
    tool_choice: str | None = None
    reasoning_effort: str | None = None
    preserve_reasoning: bool = False

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
        if self.tool_choice not in {None, "auto", "required", "none"}:
            raise ValueError("inference tool choice is invalid")
        if self.tool_choice in {"auto", "required"} and not self.tools:
            raise ValueError("tool choice requires inference tools")
        if len({item.name for item in self.tools}) != len(self.tools):
            raise ValueError("inference tool names must be unique")
        if self.reasoning_effort not in {None, "low", "medium", "high"}:
            raise ValueError("inference reasoning effort is invalid")


@dataclass(frozen=True, slots=True)
class InferenceResponse:
    content: str
    metrics: InferenceMetrics
    tool_calls: tuple[InferenceToolCall, ...] = ()
    finish_reason: str | None = None
    reasoning_content: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.content and not self.tool_calls and not self.reasoning_content
            and not self.finish_reason
        ):
            raise ValueError(
                "inference response requires content, tool calls, reasoning, or a "
                "terminal finish reason"
            )


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


class ChatInferenceRuntime(Protocol):
    """Provider-neutral boundary for text generation without residency control."""

    def chat(self, request: InferenceRequest) -> InferenceResponse: ...


class InferenceRuntime(ChatInferenceRuntime, Protocol):
    """Boundary for local runtimes that also expose model residency control."""

    def unload(self, model_ref: str) -> None:
        """Return only after the runtime no longer reports the model as loaded."""
        ...

    def prewarm(self, model_ref: str, keep_alive: str = "10m") -> None:
        """Load a model without inference content and prove it is resident."""
        ...

    def loaded_models(self) -> tuple[LoadedModel, ...]: ...
