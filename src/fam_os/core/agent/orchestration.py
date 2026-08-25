"""Typed state compilation, verification, and recovery for agent graph turns."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from fam_os.core.agent.contracts import (
    AgentGoalLedger,
    AgentToolDescriptor,
    AgentToolResult,
)
from fam_os.core.ports.inference import InferenceMessage, MessageRole


@dataclass(frozen=True, slots=True)
class AgentVerification:
    accepted: bool
    evidence: tuple[dict[str, object], ...]
    reason: str


class EvidenceVerifier:
    """Derive completion evidence from the environment, never model self-report."""

    def evaluate(self, results: tuple[AgentToolResult, ...]) -> AgentVerification:
        evidence = []
        for result in results:
            if not result.succeeded:
                continue
            postcondition = result.postcondition or {}
            semantic = postcondition.get("verified") is True
            command = result.tool_id == "verify_command"
            if semantic or command:
                evidence.append({
                    "call_id": result.call_id,
                    "tool": result.tool_id,
                    "kind": "semantic_postcondition" if semantic else "command",
                    "postcondition": postcondition,
                })
        accepted = bool(evidence)
        return AgentVerification(
            accepted,
            tuple(evidence),
            "Environment verification is present." if accepted else
            "No successful semantic postcondition or verification command is present.",
        )


@dataclass(frozen=True, slots=True)
class RecoveryDirective:
    category: str
    instruction: str
    retry_limit: int
    fingerprint: str


class RecoveryRouter:
    """Turn raw failures into bounded, actionable recovery state."""

    def classify(self, result: AgentToolResult) -> RecoveryDirective:
        lowered = result.output.casefold()
        fingerprint = hashlib.sha256(json.dumps({
            "tool": result.tool_id,
            "output": result.output[:2_000],
        }, sort_keys=True).encode()).hexdigest()[:20]
        if "invalid json" in lowered or "schema" in lowered or "arguments" in lowered:
            return RecoveryDirective(
                "malformed_tool_call",
                "Repair the call once using the offered JSON schema and validation error.",
                1, fingerprint,
            )
        if "execvp" in lowered or "command not found" in lowered or "missing executable" in lowered:
            return RecoveryDirective(
                "missing_executable",
                "Inspect project manifests and available commands; choose an installed project-native alternative.",
                1, fingerprint,
            )
        if "filenotfounderror" in lowered or "no such file" in lowered:
            return RecoveryDirective(
                "invalid_path",
                "List the nearest existing directory and retry with an exact returned path.",
                2, fingerprint,
            )
        if "exceeds" in lowered and ("bound" in lowered or "large" in lowered):
            return RecoveryDirective(
                "oversized_result",
                "Read a bounded range or narrower target and retain the evidence reference.",
                2, fingerprint,
            )
        if "path must stay inside" in lowered or "path escapes" in lowered:
            return RecoveryDirective(
                "path_escape",
                "Use a workspace-relative path; use '.' for the selected workspace root.",
                1, fingerprint,
            )
        return RecoveryDirective(
            "tool_failure",
            "Change the arguments or strategy using the concrete error before retrying.",
            2, fingerprint,
        )


@dataclass(frozen=True, slots=True)
class CompiledAgentContext:
    messages: tuple[InferenceMessage, ...]
    generation: int
    compacted: bool
    reset: bool


class AgentContextCompiler:
    """Compile model context from durable typed state and bounded recent evidence."""

    def compile(
        self, *, system: str, ledger: AgentGoalLedger, profile: str,
        prior_context: str, conversation_history: str,
        event_messages: tuple[InferenceMessage, ...],
        tool_results: tuple[AgentToolResult, ...],
        descriptors: tuple[AgentToolDescriptor, ...], context_tokens: int,
        maximum_output_tokens: int, generation: int,
        compaction_count: int,
    ) -> CompiledAgentContext:
        maximum_bytes = self._maximum_bytes(
            descriptors, context_tokens, maximum_output_tokens,
        )
        anchor = InferenceMessage(MessageRole.SYSTEM, system)
        changed_files = tuple(dict.fromkeys(
            str(item.postcondition["path"])
            for item in tool_results
            if item.succeeded and item.postcondition
            and item.postcondition.get("operation") in {
                "write_file", "create_directory", "delete_path",
            } and item.postcondition.get("path")
        ))
        latest_observations = tuple({
            "tool": item.tool_id, "succeeded": item.succeeded,
            "output": self._bounded(item.output, 2_048),
            "postcondition": item.postcondition,
        } for item in tool_results[-6:])
        unresolved_errors = tuple(
            self._bounded(item.output, 2_048)
            for item in tool_results[-6:] if not item.succeeded
        )
        state = InferenceMessage(MessageRole.USER, json.dumps({
            "goal_ledger": {
                "original_request": ledger.original_request,
                "accepted_plan": ledger.accepted_plan,
                "current_objective": ledger.current_objective,
                "completed_objectives": ledger.completed_objectives,
                "unresolved_items": ledger.unresolved_items,
            },
            "authority_profile": profile,
            "workspace_context": self._bounded(prior_context, 8_192),
            "conversation_evidence": self._bounded(conversation_history, 8_192),
            "prior_context": self._bounded(prior_context, 8_192),
            "conversation_history": self._bounded(conversation_history, 8_192),
            "changed_files": changed_files,
            "latest_observations": latest_observations,
            "unresolved_errors": unresolved_errors,
        }, sort_keys=True, separators=(",", ":")))
        values = [anchor, state, *event_messages]
        if self._size(values) <= maximum_bytes:
            return CompiledAgentContext(tuple(values), generation, False, False)

        recent: list[InferenceMessage] = []
        remaining = max(2_048, maximum_bytes - self._size([anchor, state]) - 1_024)
        for item in reversed(event_messages):
            size = len(item.content.encode("utf-8"))
            if size <= remaining:
                recent.append(item)
                remaining -= size
        omitted = len(event_messages) - len(recent)
        summary = InferenceMessage(MessageRole.SYSTEM, json.dumps({
            "context_compaction": {
                "generation": generation + 1,
                "omitted_events": omitted,
                "instruction": "Continue from the goal ledger and retained evidence.",
            }
        }, separators=(",", ":")))
        reset = compaction_count >= 2
        if reset:
            return CompiledAgentContext(
                (anchor, state, summary), generation + 1, True, True,
            )
        return CompiledAgentContext(
            (anchor, state, summary, *reversed(recent)),
            generation + 1, True, reset,
        )

    @staticmethod
    def _maximum_bytes(descriptors, context_tokens, maximum_output_tokens) -> int:
        tool_bytes = len(json.dumps([
            {"name": item.tool_id, "description": item.description,
             "parameters": item.input_schema} for item in descriptors
        ], sort_keys=True, separators=(",", ":")).encode())
        return max(8_192, (context_tokens - maximum_output_tokens) * 3 - tool_bytes)

    @staticmethod
    def _size(messages) -> int:
        return sum(len(item.content.encode("utf-8")) for item in messages)

    @staticmethod
    def _bounded(value: str, maximum_bytes: int) -> str:
        encoded = value.encode()
        if len(encoded) <= maximum_bytes:
            return value
        marker = b"\n[context truncated; full evidence remains durable]"
        return (encoded[:maximum_bytes - len(marker)] + marker).decode(
            "utf-8", errors="ignore",
        )
