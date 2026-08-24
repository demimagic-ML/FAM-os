"""Typed contracts for persistent iterative local-model agent turns."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AgentAuthorityProfile(StrEnum):
    ASK = "ask"
    WORKSPACE = "workspace"
    FULL_OS = "full_os"


class AgentToolEffect(StrEnum):
    OBSERVE = "observe"
    WORKSPACE_WRITE = "workspace_write"
    COMMAND = "command"
    NETWORK = "network"
    OS_WRITE = "os_write"


@dataclass(frozen=True, slots=True)
class AgentToolDescriptor:
    tool_id: str
    description: str
    effect: AgentToolEffect
    input_schema: dict[str, object]

    def __post_init__(self) -> None:
        if not self.tool_id.strip() or not self.description.strip():
            raise ValueError("agent tool descriptor text is invalid")
        if not isinstance(self.effect, AgentToolEffect):
            raise ValueError("agent tool effect is invalid")
        if self.input_schema.get("type") != "object":
            raise ValueError("agent tool schema must describe an object")


@dataclass(frozen=True, slots=True)
class AgentToolCall:
    call_id: str
    tool_id: str
    arguments: dict[str, object]
    reason: str

    def __post_init__(self) -> None:
        if not self.call_id.strip() or not self.tool_id.strip() or not self.reason.strip():
            raise ValueError("agent tool call text is invalid")


@dataclass(frozen=True, slots=True)
class AgentToolResult:
    call_id: str
    tool_id: str
    succeeded: bool
    output: str

    def __post_init__(self) -> None:
        if not self.call_id.strip() or not self.tool_id.strip():
            raise ValueError("agent tool result identity is invalid")
        if len(self.output.encode("utf-8")) > 262_144:
            raise ValueError("agent tool result exceeds its bound")


@dataclass(frozen=True, slots=True)
class AgentFinalResponse:
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("agent final response must not be empty")


AgentModelDecision = AgentToolCall | AgentFinalResponse


@dataclass(frozen=True, slots=True)
class AgentTurnOutcome:
    thread_id: str
    turn_id: str
    response: AgentFinalResponse
    tool_results: tuple[AgentToolResult, ...]
    model_steps: int

