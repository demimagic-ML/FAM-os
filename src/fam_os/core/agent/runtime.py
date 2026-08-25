"""Provider-neutral model/tool loop for local coding and OS agents."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from fam_os.core.agent.contracts import (
    AgentAuthorityProfile,
    AgentExecutionCheckpoint,
    AgentFinalResponse,
    AgentGoalLedger,
    AgentGraphNode,
    AgentModelDecision,
    AgentToolCall,
    AgentToolDescriptor,
    AgentToolEffect,
    AgentToolExecution,
    AgentToolResult,
    AgentTurnOutcome,
)
from fam_os.core.agent.orchestration import (
    AgentContextCompiler,
    EvidenceVerifier,
    RecoveryRouter,
)
from fam_os.core.ports.inference import (
    ChatInferenceRuntime,
    InferenceMessage,
    InferenceRequest,
    InferenceTool,
    InferenceToolCall,
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

    def goal_ledger(self, thread_id: str) -> AgentGoalLedger: ...

    def context_state(self, thread_id: str) -> tuple[int, int]: ...

    def record_compaction(self, thread_id: str, generation: int) -> None: ...

    def checkpoint(self, checkpoint: AgentExecutionCheckpoint) -> None: ...

    def latest_checkpoint(
        self, thread_id: str, turn_id: str | None = None,
    ) -> AgentExecutionCheckpoint | None: ...

    def restore_turn(
        self, thread_id: str, turn_id: str,
    ) -> tuple[tuple[AgentToolCall, AgentToolResult], ...]: ...


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

    def contains(self, tool_id: str) -> bool:
        return tool_id in self._tools

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
    keep_alive: str = "30m"
    fallback_model_ref: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.model_ref.strip() or not 1 <= self.maximum_steps <= 256
            or not 1_024 <= self.context_tokens
            or not 1_024 <= self.maximum_tool_message_bytes <= 65_536
            or not self.keep_alive.strip()
            or (
                self.fallback_model_ref is not None
                and not self.fallback_model_ref.strip()
            )
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
        self._context_compiler = AgentContextCompiler()
        self._recovery_router = RecoveryRouter()
        self._evidence_verifier = EvidenceVerifier()

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
        self._install_capability_discovery()
        self._store.begin_turn(thread_id, turn_id, objective, profile)
        ledger_reader = getattr(self._store, "goal_ledger", None)
        ledger = (
            ledger_reader(thread_id) if callable(ledger_reader)
            else AgentGoalLedger(objective, "", objective)
        )
        native_tools = bool(getattr(self._runtime, "supports_native_tools", False))
        messages = list(_initial_messages(
            objective, prior_context, history, profile, self._tools.descriptors(),
            native_tools=native_tools,
        ))
        results: list[AgentToolResult] = []
        decision_counts: dict[str, int] = {}
        retry_limits: dict[str, int] = {}
        escalated = [False]
        checkpoint_sequence = [0]
        start_step = 1
        latest_reader = getattr(self._store, "latest_checkpoint", None)
        latest = (
            latest_reader(thread_id, turn_id) if callable(latest_reader) else None
        )
        if latest is None:
            self._checkpoint(
                thread_id, turn_id, checkpoint_sequence, AgentGraphNode.PREPARE,
                0, "exploration", {
                    "objective": objective,
                    "original_request": ledger.original_request,
                    "accepted_plan": ledger.accepted_plan,
                },
            )
        else:
            checkpoint_sequence[0] = latest.sequence
            restored_reader = getattr(self._store, "restore_turn", None)
            restored = (
                restored_reader(thread_id, turn_id)
                if callable(restored_reader) else ()
            )
            for call, result in restored:
                signature = json.dumps({
                    "tool": call.tool_id, "arguments": call.arguments,
                }, sort_keys=True, separators=(",", ":"))
                decision_counts[signature] = decision_counts.get(signature, 0) + 1
                if not result.succeeded:
                    retry_limits[signature] = self._recovery_router.classify(
                        result,
                    ).retry_limit
                results.append(result)
                if native_tools:
                    messages.append(InferenceMessage(
                        MessageRole.ASSISTANT, "Resuming the persisted tool action.",
                        tool_calls=(InferenceToolCall(
                            call.call_id, call.tool_id, call.arguments,
                        ),),
                    ))
                    messages.append(InferenceMessage(
                        MessageRole.TOOL, _tool_message(
                            result, self._settings.maximum_tool_message_bytes,
                        ), tool_call_id=result.call_id, tool_name=result.tool_id,
                    ))
                else:
                    messages.append(InferenceMessage(
                        MessageRole.USER,
                        json.dumps({
                            "type": "restored_tool_result",
                            "call_id": result.call_id,
                            "tool": result.tool_id,
                            "succeeded": result.succeeded,
                            "output": result.output,
                            "postcondition": result.postcondition,
                        }, sort_keys=True, separators=(",", ":")),
                    ))
            start_step = max(1, latest.step + 1)
        try:
            return self._run_steps(
                thread_id, turn_id, objective, profile, messages, results,
                decision_counts, native_tools, ledger, prior_context, history,
                checkpoint_sequence, retry_limits,
                start_step, escalated,
            )
        except AgentTurnCancelled as error:
            cancel = getattr(self._store, "cancel_turn", None)
            if callable(cancel):
                cancel(thread_id, turn_id, str(error))
            else:
                self._store.fail_turn(thread_id, turn_id, str(error))
            self._checkpoint(
                thread_id, turn_id, checkpoint_sequence, AgentGraphNode.FAILED,
                0, _agent_phase(results), {"cancelled": True, "reason": str(error)},
            )
            raise
        except Exception as error:
            self._store.fail_turn(
                thread_id, turn_id, f"{type(error).__name__}: {str(error)[:2_000]}",
            )
            self._checkpoint(
                thread_id, turn_id, checkpoint_sequence, AgentGraphNode.FAILED,
                0, _agent_phase(results), {"failure": str(error)[:2_000]},
            )
            raise

    def _install_capability_discovery(self) -> None:
        descriptors = self._tools.descriptors()
        if len(descriptors) <= 8 or self._tools.contains("request_capabilities"):
            return
        available = tuple(item.tool_id for item in descriptors)
        self._tools.register(AgentToolDescriptor(
            "request_capabilities",
            "Request exposure of additional registered tools when the current set "
            "cannot perform the next necessary action. Hidden tool identifiers: "
            + ", ".join(available) + ".",
            AgentToolEffect.OBSERVE,
            {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                },
                "required": ["reason"],
            },
        ), lambda _arguments: json.dumps({
            "additional_tools_available": available,
            "instruction": "The next inference step will expose the full tool set.",
        }, separators=(",", ":")))

    def _run_steps(
        self, thread_id, turn_id, objective, profile, messages, results,
        decision_counts, native_tools, ledger, prior_context, history,
        checkpoint_sequence, retry_limits,
        start_step, escalated,
    ):
        context_reader = getattr(self._store, "context_state", None)
        generation, compaction_count = (
            context_reader(thread_id) if callable(context_reader) else (0, 0)
        )
        capabilities_expanded = start_step > 1
        for step in range(start_step, self._settings.maximum_steps + 1):
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
            descriptors = _phase_tools(
                self._tools.descriptors(), results, capabilities_expanded,
            )
            phase = _agent_phase(results)
            active_model_ref = _active_model_ref(
                self._settings, results, escalated[0],
            )
            phased = _messages_with_phase(messages, phase)
            compiled = self._context_compiler.compile(
                system=phased[0].content, ledger=ledger, profile=profile.value,
                prior_context=prior_context, conversation_history=history,
                event_messages=tuple(phased[2:]), tool_results=tuple(results),
                descriptors=descriptors,
                context_tokens=self._settings.context_tokens,
                maximum_output_tokens=self._settings.maximum_output_tokens,
                generation=generation, compaction_count=compaction_count,
            )
            request_messages = compiled.messages
            request_context_tokens = _request_context_tokens(
                request_messages, self._settings.context_tokens,
                self._settings.maximum_output_tokens,
            )
            if compiled.compacted and compiled.generation != generation:
                generation = compiled.generation
                compaction_count += 1
                recorder = getattr(self._store, "record_compaction", None)
                if callable(recorder):
                    recorder(thread_id, generation)
            self._checkpoint(
                thread_id, turn_id, checkpoint_sequence, AgentGraphNode.INFER,
                step, phase, {
                    "context_generation": generation,
                    "compacted": compiled.compacted,
                    "clean_reset": compiled.reset,
                    "tool_count": len(descriptors),
                    "result_count": len(results),
                    "model_ref": active_model_ref,
                    "escalated": active_model_ref != self._settings.model_ref,
                    "request_context_tokens": request_context_tokens,
                },
            )
            response = self._runtime.chat(InferenceRequest(
                model_ref=active_model_ref,
                messages=request_messages,
                context_tokens=request_context_tokens,
                max_output_tokens=self._settings.maximum_output_tokens,
                keep_alive=self._settings.keep_alive,
                json_output=not native_tools,
                temperature=0.0,
                seed=42,
                tools=(
                    _native_tools(descriptors)
                    if native_tools else ()
                ),
                tool_choice="auto" if native_tools and descriptors else None,
                reasoning_effort=_reasoning_effort(active_model_ref, phase),
                preserve_reasoning=_preserve_reasoning(active_model_ref),
            ))
            if not response.content and not response.tool_calls:
                signature = "model:empty_visible_response"
                decision_counts[signature] = decision_counts.get(signature, 0) + 1
                if decision_counts[signature] > 1:
                    raise RuntimeError(
                        "model repeatedly returned no visible action or answer"
                    )
                messages.append(InferenceMessage(
                    MessageRole.ASSISTANT, "No visible action or answer was emitted.",
                    reasoning_content=(
                        response.reasoning_content
                        if _preserve_reasoning(active_model_ref) else None
                    ),
                ))
                messages.append(InferenceMessage(
                    MessageRole.USER,
                    json.dumps({
                        "type": "model_response_repair",
                        "reason": "The prior response had no visible action or answer.",
                        "instruction": (
                            "Emit exactly one offered tool call or a visible final answer."
                        ),
                    }, separators=(",", ":")),
                ))
                self._checkpoint(
                    thread_id, turn_id, checkpoint_sequence,
                    AgentGraphNode.RECOVER, step, phase, {
                        "category": "empty_visible_response",
                        "retry_limit": 1,
                    },
                )
                capabilities_expanded = True
                if self._settings.fallback_model_ref is not None:
                    escalated[0] = True
                continue
            if native_tools and response.tool_calls:
                messages.append(InferenceMessage(
                    MessageRole.ASSISTANT, response.content,
                    tool_calls=response.tool_calls,
                    reasoning_content=(
                        response.reasoning_content
                        if _preserve_reasoning(active_model_ref) else None
                    ),
                ))
                for index, native_call in enumerate(response.tool_calls, 1):
                    decision = AgentToolCall(
                        f"{native_call.call_id or 'native-call'}-{step}-{index}",
                        native_call.name, native_call.arguments,
                        "Selected through native model tool calling.",
                    )
                    self._checkpoint(
                        thread_id, turn_id, checkpoint_sequence,
                        AgentGraphNode.EXECUTE, step, phase, {
                            "call_id": decision.call_id, "tool": decision.tool_id,
                            "arguments": decision.arguments,
                        },
                    )
                    result, repeated, blocked = self._invoke_tool(
                        thread_id, turn_id, profile, decision, decision_counts,
                        retry_limits,
                    )
                    results.append(result)
                    self._record_observation_checkpoint(
                        thread_id, turn_id, checkpoint_sequence, step, phase,
                        result, repeated,
                    )
                    messages.append(InferenceMessage(
                        MessageRole.TOOL, _tool_message(
                            result, self._settings.maximum_tool_message_bytes,
                        ),
                        tool_call_id=result.call_id, tool_name=result.tool_id,
                    ))
                    if blocked:
                        messages.append(_repeat_intervention())
                continue
            decision = (
                AgentFinalResponse(response.content)
                if native_tools else parse_agent_decision(response.content, step)
            )
            messages.append(InferenceMessage(
                MessageRole.ASSISTANT, response.content,
                reasoning_content=(
                    response.reasoning_content
                    if _preserve_reasoning(active_model_ref) else None
                ),
            ))
            if isinstance(decision, AgentFinalResponse):
                verification = self._evidence_verifier.evaluate(tuple(results))
                self._checkpoint(
                    thread_id, turn_id, checkpoint_sequence, AgentGraphNode.VERIFY,
                    step, phase, {
                        "accepted": verification.accepted,
                        "reason": verification.reason,
                        "evidence": list(verification.evidence),
                    },
                )
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
                    capabilities_expanded = True
                    if self._settings.fallback_model_ref is not None:
                        escalated[0] = True
                    continue
                self._store.complete_turn(thread_id, turn_id, decision)
                self._checkpoint(
                    thread_id, turn_id, checkpoint_sequence, AgentGraphNode.COMPLETE,
                    step, phase, {
                        "response": decision.content,
                        "verified_evidence_count": len(verification.evidence),
                    },
                )
                return AgentTurnOutcome(
                    thread_id, turn_id, decision, tuple(results), step,
                )
            self._checkpoint(
                thread_id, turn_id, checkpoint_sequence, AgentGraphNode.EXECUTE,
                step, phase, {
                    "call_id": decision.call_id, "tool": decision.tool_id,
                    "arguments": decision.arguments,
                },
            )
            result, repeated, blocked = self._invoke_tool(
                thread_id, turn_id, profile, decision, decision_counts,
                retry_limits,
            )
            results.append(result)
            self._record_observation_checkpoint(
                thread_id, turn_id, checkpoint_sequence, step, phase,
                result, repeated,
            )
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
            if blocked:
                messages.append(_repeat_intervention())
        raise RuntimeError("agent turn exhausted its model-step budget")

    def _record_observation_checkpoint(
        self, thread_id, turn_id, sequence, step, phase, result, repeated,
    ) -> None:
        self._checkpoint(
            thread_id, turn_id, sequence, AgentGraphNode.OBSERVE,
            step, phase, {
                "call_id": result.call_id, "tool": result.tool_id,
                "succeeded": result.succeeded,
                "postcondition": result.postcondition,
                "output_preview": result.output[:2_000],
            },
        )
        if not result.succeeded:
            directive = self._recovery_router.classify(result)
            self._checkpoint(
                thread_id, turn_id, sequence, AgentGraphNode.RECOVER,
                step, phase, {
                    "category": directive.category,
                    "instruction": directive.instruction,
                    "retry_limit": directive.retry_limit,
                    "fingerprint": directive.fingerprint,
                    "attempt": repeated,
                },
            )

    def _checkpoint(
        self, thread_id, turn_id, sequence, node, step, phase, state,
    ) -> None:
        writer = getattr(self._store, "checkpoint", None)
        if not callable(writer):
            return
        sequence[0] += 1
        writer(AgentExecutionCheckpoint(
            thread_id, turn_id, sequence[0], node, step, phase, state,
        ))

    def _invoke_tool(
        self, thread_id, turn_id, profile, decision, decision_counts,
        retry_limits,
    ):
        self._store.record_call(thread_id, turn_id, decision)
        signature = _decision_signature(decision)
        decision_counts[signature] = decision_counts.get(signature, 0) + 1
        repeated = decision_counts[signature]
        blocked = repeated > retry_limits.get(signature, 1) + 1
        if blocked:
            result = AgentToolResult(
                decision.call_id, decision.tool_id, False,
                "Repeated-call loop detected. This action has already produced the "
                "same result; inspect different evidence or choose another strategy.",
            )
        else:
            result = self._tools.invoke(decision, profile)
        if not result.succeeded:
            recovery = self._recovery_router.classify(result)
            retry_limits[signature] = recovery.retry_limit
            result = AgentToolResult(
                result.call_id, result.tool_id, False,
                f"{result.output}\nstructured_recovery=" + json.dumps({
                    "category": recovery.category,
                    "instruction": recovery.instruction,
                    "retry_limit": recovery.retry_limit,
                    "fingerprint": recovery.fingerprint,
                }, sort_keys=True, separators=(",", ":")),
                result.postcondition,
            )
        self._store.record_result(thread_id, turn_id, result)
        return result, repeated, blocked


def _decision_signature(decision: AgentToolCall) -> str:
    return json.dumps({
        "tool": decision.tool_id, "arguments": decision.arguments,
    }, sort_keys=True, separators=(",", ":"))


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
        "The goal_ledger is authoritative durable task state. Resolve referential "
        "follow-ups such as 'do it', 'continue', or 'implement the plan' against its "
        "accepted_plan and original_request; do not repeat the plan as the answer. "
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
    if any(
        item.succeeded and item.tool_id == "verify_command" for item in results
    ):
        return "finalization"
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


def _active_model_ref(
    settings: IterativeAgentSettings, results, escalated: bool,
) -> str:
    fallback = settings.fallback_model_ref
    if fallback is None or fallback.casefold() == settings.model_ref.casefold():
        return settings.model_ref
    failed_actions = sum(not item.succeeded for item in results)
    return fallback if escalated or failed_actions >= 2 else settings.model_ref


def _request_context_tokens(messages, maximum: int, output_tokens: int) -> int:
    prompt_bytes = sum(len(item.content.encode("utf-8")) for item in messages)
    estimated_prompt_tokens = (prompt_bytes + 2) // 3
    required = estimated_prompt_tokens + output_tokens + 2_048
    for bucket in (8_192, 16_384, 32_768, 65_536, 131_072):
        if required <= bucket:
            return min(bucket, maximum)
    return maximum


def _phase_tools(descriptors, results, expand=False):
    phase = _agent_phase(results)
    if phase == "finalization":
        return ()
    if phase == "verification":
        return tuple(descriptors)
    if expand or phase == "implementation" or any(
        item.succeeded and item.tool_id == "request_capabilities" for item in results
    ):
        return tuple(item for item in descriptors if item.tool_id != "verify_command")
    core = {
        "list_directory", "read_file", "search_text", "write_file",
        "create_directory", "observe_application", "request_capabilities",
    }
    selected = tuple(
        item for item in descriptors
        if item.tool_id in core and item.tool_id != "verify_command"
    )
    return selected or tuple(
        item for item in descriptors if item.tool_id != "verify_command"
    )


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
    if phase == "verification":
        return (
        "Current phase: verify the requested outcome. A successful semantic "
        "postcondition from a filesystem tool is already verification evidence."
        )
    return (
        "Current phase: finalization. The verification command succeeded. Return "
        "a concise visible final answer now; do not perform more exploratory work."
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


def _reasoning_effort(model_ref: str, phase: str) -> str | None:
    if "qwen3.8" not in model_ref.casefold():
        return None
    if phase in {"implementation", "verification"}:
        return "medium"
    return "low"


def _preserve_reasoning(model_ref: str) -> bool:
    return "qwen3.8" in model_ref.casefold()
