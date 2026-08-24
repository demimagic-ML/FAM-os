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
    AgentToolExecution,
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
        postcondition = None
        if isinstance(output, AgentToolExecution):
            postcondition = output.postcondition
            output = output.output
        if not isinstance(output, str):
            raise TypeError("agent tool implementation must return text or execution")
        return AgentToolResult(
            call.call_id, call.tool_id, True, _bounded_tool_output(output),
            postcondition,
        )


@dataclass(frozen=True, slots=True)
class IterativeAgentSettings:
    model_ref: str
    maximum_steps: int = 64
    context_tokens: int = 32_768
    maximum_output_tokens: int = 4_096
    maximum_tool_message_bytes: int = 16_384

    def __post_init__(self) -> None:
        if (
            not self.model_ref.strip() or not 1 <= self.maximum_steps <= 256
            or not 1_024 <= self.context_tokens
            or not 1_024 <= self.maximum_tool_message_bytes <= 65_536
        ):
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
            descriptors = _phase_tools(self._tools.descriptors(), results)
            phase = _agent_phase(results)
            request_messages = _budgeted_messages(
                _messages_with_phase(messages, phase),
                context_tokens=self._settings.context_tokens,
                maximum_output_tokens=self._settings.maximum_output_tokens,
                descriptors=descriptors,
            )
            response = self._runtime.chat(InferenceRequest(
                model_ref=self._settings.model_ref,
                messages=request_messages,
                context_tokens=self._settings.context_tokens,
                max_output_tokens=self._settings.maximum_output_tokens,
                json_output=not native_tools,
                temperature=0.0,
                seed=42,
                tools=(
                    _native_tools(descriptors)
                    if native_tools else ()
                ),
                tool_choice="auto" if native_tools and descriptors else None,
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
                        MessageRole.TOOL, _tool_message(
                            result, self._settings.maximum_tool_message_bytes,
                        ),
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
        if not result.succeeded:
            result = AgentToolResult(
                result.call_id, result.tool_id, False,
                f"{result.output}\nstructured_recovery={_recovery_guidance(result)}",
                result.postcondition,
            )
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


def _bounded_tool_output(output: str, maximum_bytes: int = 262_144) -> str:
    encoded = output.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return output
    marker = b"\n[tool output truncated by FAM_OS]"
    retained = encoded[:maximum_bytes - len(marker)]
    return retained.decode("utf-8", "ignore") + marker.decode("ascii")


def _tool_message(result: AgentToolResult, maximum_bytes: int) -> str:
    output = _bounded_tool_output(result.output, maximum_bytes)
    if result.postcondition is None:
        return output
    return json.dumps({
        "output": output,
        "postcondition": result.postcondition,
    }, sort_keys=True, separators=(",", ":"))


def _agent_phase(results) -> str:
    if any(item.succeeded and item.postcondition for item in results):
        return "verification"
    if any(item.succeeded and item.tool_id in {
        "write_file", "create_directory", "delete_path", "move_path",
        "apply_patch", "run_command",
    } for item in results):
        return "verification"
    if any(item.succeeded for item in results):
        return "implementation"
    return "exploration"


def _phase_tools(descriptors, results):
    phase = _agent_phase(results)
    hidden = set() if phase == "verification" else {"verify_command"}
    return tuple(item for item in descriptors if item.tool_id not in hidden)


def _phase_instruction(phase: str) -> str:
    if phase == "exploration":
        return (
            "Current phase: explore only as much as needed. For a simple explicit "
            "filesystem objective, perform the direct filesystem action immediately."
        )
    if phase == "implementation":
        return (
            "Current phase: implement the smallest coherent change using file tools; "
            "do not return another plan."
        )
    return (
        "Current phase: verify the requested outcome. A successful semantic "
        "postcondition from a filesystem tool is already verification evidence."
    )


def _messages_with_phase(messages, phase: str):
    values = list(messages)
    if not values:
        return ()
    first = values[0]
    values[0] = InferenceMessage(
        first.role, f"{first.content}\n\n{_phase_instruction(phase)}",
        images=first.images, tool_calls=first.tool_calls,
        tool_call_id=first.tool_call_id, tool_name=first.tool_name,
    )
    return tuple(values)


def _budgeted_messages(
    messages, *, context_tokens: int, maximum_output_tokens: int, descriptors,
):
    tool_bytes = len(json.dumps([
        {"name": item.tool_id, "description": item.description,
         "parameters": item.input_schema}
        for item in descriptors
    ], sort_keys=True, separators=(",", ":")).encode("utf-8"))
    maximum_bytes = max(
        8_192, (context_tokens - maximum_output_tokens) * 3 - tool_bytes,
    )
    values = list(messages)
    if len(values) >= 2:
        values[1] = _compact_initial_user(values[1], maximum_bytes // 3)
    total = sum(len(item.content.encode("utf-8")) for item in values)
    if total <= maximum_bytes:
        return tuple(values)
    preserved = values[:2]
    recent = []
    used = sum(len(item.content.encode("utf-8")) for item in preserved)
    remaining = max(2_048, maximum_bytes - used - 1_024)
    for item in reversed(values[2:]):
        size = len(item.content.encode("utf-8"))
        if size > remaining:
            if not recent and remaining >= 512:
                recent.append(_message_with_content(
                    item, _bounded_tool_output(item.content, remaining),
                ))
                remaining = 0
            continue
        recent.append(item)
        remaining -= size
    dropped = max(0, len(values) - len(preserved) - len(recent))
    summary = InferenceMessage(
        MessageRole.SYSTEM,
        f"Context compacted: {dropped} older messages were omitted. Preserve the "
        "original objective and continue from the latest retained tool evidence.",
    )
    return tuple((*preserved, summary, *reversed(recent)))


def _message_with_content(message: InferenceMessage, content: str):
    return InferenceMessage(
        message.role, content, images=message.images,
        tool_calls=message.tool_calls, tool_call_id=message.tool_call_id,
        tool_name=message.tool_name,
    )


def _compact_initial_user(message: InferenceMessage, maximum_bytes: int):
    if len(message.content.encode("utf-8")) <= maximum_bytes:
        return message
    try:
        value = json.loads(message.content)
    except (json.JSONDecodeError, TypeError):
        return InferenceMessage(
            message.role, _bounded_tool_output(message.content, maximum_bytes),
        )
    if not isinstance(value, dict):
        return message
    for key in ("conversation_history", "prior_context"):
        content = value.get(key)
        if isinstance(content, str) and len(content.encode("utf-8")) > 2_048:
            value[key] = _bounded_tool_output(content, 2_048)
    compacted = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return InferenceMessage(message.role, compacted)


def _recovery_guidance(result: AgentToolResult) -> str:
    lowered = result.output.casefold()
    if (
        "execvp" in lowered or "command not found" in lowered
        or "missing executable" in lowered
    ):
        return (
            "The executable is unavailable. Inspect project manifests and scripts, "
            "then use an installed equivalent; do not repeat the same command."
        )
    if "filenotfounderror" in lowered or "no such file" in lowered:
        return (
            "The path was not found. Use list_directory with path '.' and retry with "
            "an exact relative path from that result."
        )
    elif "path must stay inside" in lowered or "path escapes" in lowered:
        return (
            "The path was invalid. Use a workspace-relative path without a leading "
            "slash or '..'; use '.' for the selected folder."
        )
    else:
        return (
            "The tool failed. Change the arguments or strategy using the concrete "
            "error; do not repeat the identical call."
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
