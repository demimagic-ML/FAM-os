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
    InferenceTool,
    MessageRole,
)


class AgentTurnStore(Protocol):
    def conversation_context(self, thread_id: str) -> str: ...

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

    def fail_turn(self, thread_id: str, turn_id: str, failure: str) -> None: ...

    def cancel_turn(self, thread_id: str, turn_id: str, reason: str) -> None: ...

    def consume_controls(self, thread_id: str) -> tuple[dict[str, str], ...]: ...


class AgentTurnCancelled(RuntimeError):
    """Raised when the owner cancels an active iterative turn."""


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
        completion_validator: Callable[[tuple[AgentToolResult, ...]], str | None]
        | None = None,
        completion_reviewer: Callable[
            [str, AgentFinalResponse, tuple[AgentToolResult, ...]], str | None
        ] | None = None,
    ) -> None:
        self._runtime = runtime
        self._settings = settings
        self._tools = tools
        self._store = store
        self._completion_validator = completion_validator
        self._completion_reviewer = completion_reviewer

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
        history_reader = getattr(self._store, "conversation_context", None)
        history = history_reader(thread_id) if callable(history_reader) else ""
        self._store.begin_turn(thread_id, turn_id, objective, profile)
        native_tools = bool(getattr(self._runtime, "supports_native_tools", False))
        messages = list(_initial_messages(
            objective, prior_context, history, profile, self._tools.descriptors(),
            native_tools=native_tools,
        ))
        results: list[AgentToolResult] = []
        decision_counts: dict[str, int] = {}
        try:
            return self._run_steps(
                thread_id, turn_id, objective, profile, messages, results,
                decision_counts, native_tools,
            )
        except AgentTurnCancelled as error:
            cancel = getattr(self._store, "cancel_turn", None)
            if callable(cancel):
                cancel(thread_id, turn_id, str(error))
            else:
                self._store.fail_turn(thread_id, turn_id, str(error))
            raise
        except Exception as error:
            self._store.fail_turn(
                thread_id, turn_id, f"{type(error).__name__}: {str(error)[:2_000]}",
            )
            raise

    def _run_steps(
        self, thread_id, turn_id, objective, profile, messages, results,
        decision_counts, native_tools,
    ):
        for step in range(1, self._settings.maximum_steps + 1):
            consume = getattr(self._store, "consume_controls", None)
            controls = consume(thread_id) if callable(consume) else ()
            for control in controls:
                if control.get("kind") == "cancel":
                    raise AgentTurnCancelled(
                        control.get("content") or "Cancelled by owner.",
                    )
                if control.get("kind") == "steer":
                    messages.append(InferenceMessage(
                        MessageRole.USER,
                        json.dumps({
                            "type": "owner_guidance",
                            "instruction": control.get("content", ""),
                            "priority": "Apply this guidance to the current objective.",
                        }, sort_keys=True, separators=(",", ":")),
                    ))
            response = self._runtime.chat(InferenceRequest(
                model_ref=self._settings.model_ref,
                messages=tuple(messages),
                context_tokens=self._settings.context_tokens,
                max_output_tokens=self._settings.maximum_output_tokens,
                json_output=not native_tools,
                temperature=0.0,
                seed=42,
                tools=(
                    _native_tools(self._tools.descriptors())
                    if native_tools else ()
                ),
                tool_choice="auto" if native_tools else None,
            ))
            if native_tools and response.tool_calls:
                messages.append(InferenceMessage(
                    MessageRole.ASSISTANT, response.content,
                    tool_calls=response.tool_calls,
                ))
                for index, native_call in enumerate(response.tool_calls, 1):
                    decision = AgentToolCall(
                        native_call.call_id or f"call-{step}-{index}",
                        native_call.name, native_call.arguments,
                        "Selected through native model tool calling.",
                    )
                    result, repeated = self._invoke_tool(
                        thread_id, turn_id, profile, decision, decision_counts,
                    )
                    results.append(result)
                    messages.append(InferenceMessage(
                        MessageRole.TOOL, result.output,
                        tool_call_id=result.call_id, tool_name=result.tool_id,
                    ))
                    if repeated >= 3:
                        messages.append(_repeat_intervention())
                continue
            decision = (
                AgentFinalResponse(response.content)
                if native_tools else parse_agent_decision(response.content, step)
            )
            messages.append(InferenceMessage(MessageRole.ASSISTANT, response.content))
            if isinstance(decision, AgentFinalResponse):
                rejection = (
                    None if self._completion_validator is None
                    else self._completion_validator(tuple(results))
                )
                if rejection is None and self._completion_reviewer is not None:
                    rejection = self._completion_reviewer(
                        objective, decision, tuple(results),
                    )
                if rejection is not None:
                    signature = f"final:{decision.content}"
                    decision_counts[signature] = decision_counts.get(signature, 0) + 1
                    if decision_counts[signature] >= 4:
                        raise RuntimeError(
                            "agent repeated a rejected completion without progress"
                        )
                    messages.append(InferenceMessage(
                        MessageRole.USER,
                        json.dumps({
                            "type": "completion_rejected",
                            "reason": rejection,
                            "instruction": (
                                "Continue using tools, adapt to the observed failures, "
                                "and only finish when this condition is satisfied."
                            ),
                        }, sort_keys=True, separators=(",", ":")),
                    ))
                    continue
                self._store.complete_turn(thread_id, turn_id, decision)
                return AgentTurnOutcome(
                    thread_id, turn_id, decision, tuple(results), step,
                )
            result, repeated = self._invoke_tool(
                thread_id, turn_id, profile, decision, decision_counts,
            )
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
            if repeated >= 3:
                messages.append(_repeat_intervention())
        raise RuntimeError("agent turn exhausted its model-step budget")

    def _invoke_tool(
        self, thread_id, turn_id, profile, decision, decision_counts,
    ):
        self._store.record_call(thread_id, turn_id, decision)
        signature = json.dumps({
            "tool": decision.tool_id,
            "arguments": decision.arguments,
        }, sort_keys=True, separators=(",", ":"))
        decision_counts[signature] = decision_counts.get(signature, 0) + 1
        repeated = decision_counts[signature]
        if repeated >= 3:
            result = AgentToolResult(
                decision.call_id, decision.tool_id, False,
                "Repeated-call loop detected. This action has already produced the "
                "same result; inspect different evidence or choose another strategy.",
            )
        else:
            result = self._tools.invoke(decision, profile)
        self._store.record_result(thread_id, turn_id, result)
        return result, repeated


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


def _initial_messages(
    objective, prior_context, conversation_history, profile, descriptors, *,
    native_tools=False,
):
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
        "For coding work, inspect both the relevant implementation and its acceptance "
        "tests before editing. Preserve tests unless changing requirements explicitly "
        "require a test change. Diagnose causes rather than rewriting evidence, and run "
        "the relevant available checks after edits. Do not claim completion without a "
        "successful tool result that verifies the requested behavior. The editable "
        "workspace may be a staged candidate without repository metadata; Git tools "
        "describe the owner repository and file tools describe the candidate. Commands "
        "are direct argv, not shell syntax. If a preferred test runner is unavailable "
        "and dependency installation is not authorized, use the existing language "
        "runtime to perform a focused behavioral check instead of repeatedly installing. "
        "Treat a missing executable or rejected package installation as environment "
        "evidence: do not retry it or switch to another installer. Inspect the repository's "
        "manifests and existing scripts, then use an available equivalent or perform a "
        "focused check with the installed runtime. Optional linters are not prerequisites "
        "unless the objective explicitly asks to install them. "
        "Use run_command for setup and exploratory processes. Use verify_command for "
        "the final test, build, diagnostic, or behavioral assertion whose zero exit "
        "status proves the implementation works. "
        + (
            "Use only the native tools supplied with this request. When the objective "
            "is complete, return the concise final answer as normal assistant text. "
            if native_tools else
            "Return only one strict JSON object per step. To use a tool return "
            '{"type":"tool_call","tool":"tool id","arguments":{},"reason":"why now"}. '
            "When the objective is actually complete return "
            '{"type":"final","content":"concise outcome and verification"}. '
        )
        + "A denied tool result means request a suitable alternative or explain the exact "
        "remaining authority; never claim an effect occurred without a successful result. "
        "Only call tool identifiers present in available_tools; never invent a tool. "
        + (
            "This is a read-only question. Answer the exact question directly from file "
            "or directory evidence. Do not run builds, verification commands, package "
            "installers, or environment diagnostics unless the user explicitly asks."
            if profile is AgentAuthorityProfile.ASK else ""
        )
    )
    user = json.dumps({
        "objective": objective,
        "authority_profile": profile.value,
        "prior_context": prior_context,
        "conversation_history": conversation_history,
        "available_tools": None if native_tools else tools,
    }, sort_keys=True, separators=(",", ":"))
    return (
        InferenceMessage(MessageRole.SYSTEM, system),
        InferenceMessage(MessageRole.USER, user),
    )


def _native_tools(descriptors) -> tuple[InferenceTool, ...]:
    return tuple(
        InferenceTool(item.tool_id, item.description, item.input_schema)
        for item in descriptors
    )


def _repeat_intervention() -> InferenceMessage:
    return InferenceMessage(
        MessageRole.SYSTEM,
        "The last tool and arguments are blocked for the remainder of this turn "
        "because they repeatedly made no progress. Do not call them again. Reassess "
        "the objective from existing evidence and choose a materially different tool "
        "or approach. Missing optional tooling is not a reason to install it unless "
        "installation is itself part of the objective.",
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
