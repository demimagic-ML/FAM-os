"""Provider-neutral model/tool loop for local coding and OS agents."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from fam_os.core.agent.contracts import (
    AgentAuthorityProfile,
    AgentFinalResponse,
    AgentModelDecision,
    AgentToolCall,
    AgentToolDescriptor,
    AgentToolEffect,
    AgentToolResult,
    AgentTurnOutcome,
)
from fam_os.core.ports.inference import (
    ChatInferenceRuntime,
    InferenceMessage,
    InferenceRequest,
    MessageRole,
)


class AgentTurnStore(Protocol):
    def begin_turn(
        self, thread_id: str, turn_id: str, objective: str,
        profile: AgentAuthorityProfile,
    ) -> None: ...

    def record_call(self, thread_id: str, turn_id: str, call: AgentToolCall) -> None: ...

    def record_result(
        self, thread_id: str, turn_id: str, result: AgentToolResult,
    ) -> None: ...

    def complete_turn(
        self, thread_id: str, turn_id: str, response: AgentFinalResponse,
    ) -> None: ...


class AgentToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[
            str, tuple[AgentToolDescriptor, Callable[[dict[str, object]], str]]
        ] = {}

    def register(
        self,
        descriptor: AgentToolDescriptor,
        implementation: Callable[[dict[str, object]], str],
    ) -> None:
        if descriptor.tool_id in self._tools:
            raise ValueError("agent tool is already registered")
        self._tools[descriptor.tool_id] = (descriptor, implementation)

    def descriptors(self) -> tuple[AgentToolDescriptor, ...]:
        return tuple(self._tools[key][0] for key in sorted(self._tools))

    def invoke(
        self,
        call: AgentToolCall,
        profile: AgentAuthorityProfile,
    ) -> AgentToolResult:
        registered = self._tools.get(call.tool_id)
        if registered is None:
            return AgentToolResult(
                call.call_id, call.tool_id, False, "Unknown agent tool.",
            )
        descriptor, implementation = registered
        if not _profile_allows(profile, descriptor.effect):
            return AgentToolResult(
                call.call_id, call.tool_id, False,
                f"Authority profile {profile.value} does not allow {descriptor.effect.value}.",
            )
        try:
            output = implementation(dict(call.arguments))
        except Exception as error:
            return AgentToolResult(
                call.call_id, call.tool_id, False,
                f"{type(error).__name__}: {str(error)[:2_000]}",
            )
        if not isinstance(output, str):
            raise TypeError("agent tool implementation must return text")
        return AgentToolResult(call.call_id, call.tool_id, True, output)


@dataclass(frozen=True, slots=True)
class IterativeAgentSettings:
    model_ref: str
    maximum_steps: int = 64
    context_tokens: int = 32_768
    maximum_output_tokens: int = 4_096

    def __post_init__(self) -> None:
        if not self.model_ref.strip() or not 1 <= self.maximum_steps <= 256:
            raise ValueError("iterative agent settings are invalid")


class IterativeModelAgent:
    def __init__(
        self,
        runtime: ChatInferenceRuntime,
        settings: IterativeAgentSettings,
        tools: AgentToolRegistry,
        store: AgentTurnStore,
    ) -> None:
        self._runtime = runtime
        self._settings = settings
        self._tools = tools
        self._store = store

    def run(
        self,
        *,
        thread_id: str,
        turn_id: str,
        objective: str,
        profile: AgentAuthorityProfile,
        prior_context: str = "",
    ) -> AgentTurnOutcome:
        if not thread_id.strip() or not turn_id.strip() or not objective.strip():
            raise ValueError("agent turn identity and objective are required")
        self._store.begin_turn(thread_id, turn_id, objective, profile)
        messages = list(_initial_messages(
            objective, prior_context, profile, self._tools.descriptors(),
        ))
        results: list[AgentToolResult] = []
        for step in range(1, self._settings.maximum_steps + 1):
            response = self._runtime.chat(InferenceRequest(
                model_ref=self._settings.model_ref,
                messages=tuple(messages),
                context_tokens=self._settings.context_tokens,
                max_output_tokens=self._settings.maximum_output_tokens,
                json_output=True,
                temperature=0.0,
                seed=42,
            ))
            decision = parse_agent_decision(response.content, step)
            messages.append(InferenceMessage(MessageRole.ASSISTANT, response.content))
            if isinstance(decision, AgentFinalResponse):
                self._store.complete_turn(thread_id, turn_id, decision)
                return AgentTurnOutcome(
                    thread_id, turn_id, decision, tuple(results), step,
                )
            self._store.record_call(thread_id, turn_id, decision)
            result = self._tools.invoke(decision, profile)
            self._store.record_result(thread_id, turn_id, result)
            results.append(result)
            messages.append(InferenceMessage(
                MessageRole.USER,
                json.dumps({
                    "type": "tool_result",
                    "call_id": result.call_id,
                    "tool": result.tool_id,
                    "succeeded": result.succeeded,
                    "output": result.output,
                }, sort_keys=True, separators=(",", ":")),
            ))
        raise RuntimeError("agent turn exhausted its model-step budget")


def parse_agent_decision(content: str, step: int) -> AgentModelDecision:
    try:
        value = json.loads(content)
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError("agent model returned invalid JSON") from error
    if not isinstance(value, dict):
        raise ValueError("agent model decision must be an object")
    kind = value.get("type")
    if kind == "final" and set(value) == {"type", "content"}:
        if not isinstance(value["content"], str):
            raise ValueError("agent final content must be text")
        return AgentFinalResponse(value["content"])
    if kind == "tool_call" and set(value) == {
        "type", "tool", "arguments", "reason",
    }:
        tool, arguments, reason = value["tool"], value["arguments"], value["reason"]
        if not isinstance(tool, str) or not isinstance(arguments, dict) or not isinstance(reason, str):
            raise ValueError("agent tool call fields are invalid")
        return AgentToolCall(f"call-{step}", tool, arguments, reason)
    raise ValueError("agent model decision schema is invalid")


def _initial_messages(objective, prior_context, profile, descriptors):
    tools = [{
        "tool": item.tool_id,
        "description": item.description,
        "effect": item.effect.value,
        "input_schema": item.input_schema,
    } for item in descriptors]
    system = (
        "You are an iterative local coding and operating-system agent. Work toward "
        "the objective by choosing one tool at a time, observing its real result, and "
        "adapting. Do not stop at a plan when the objective requests implementation. "
        "Return only one strict JSON object per step. To use a tool return "
        '{"type":"tool_call","tool":"tool id","arguments":{},"reason":"why now"}. '
        "When the objective is actually complete return "
        '{"type":"final","content":"concise outcome and verification"}. '
        "A denied tool result means request a suitable alternative or explain the exact "
        "remaining authority; never claim an effect occurred without a successful result."
    )
    user = json.dumps({
        "objective": objective,
        "authority_profile": profile.value,
        "prior_context": prior_context,
        "available_tools": tools,
    }, sort_keys=True, separators=(",", ":"))
    return (
        InferenceMessage(MessageRole.SYSTEM, system),
        InferenceMessage(MessageRole.USER, user),
    )


def _profile_allows(
    profile: AgentAuthorityProfile, effect: AgentToolEffect,
) -> bool:
    if effect is AgentToolEffect.OBSERVE:
        return True
    if profile is AgentAuthorityProfile.ASK:
        return False
    if profile is AgentAuthorityProfile.WORKSPACE:
        return effect in {
            AgentToolEffect.WORKSPACE_WRITE,
            AgentToolEffect.COMMAND,
        }
    return True
