"""Model-driven resolution of conversational turns before task routing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from fam_os.core.ports.inference import (
    ChatInferenceRuntime,
    InferenceMessage,
    InferenceRequest,
    MessageRole,
)


class TurnDisposition(StrEnum):
    GENERAL_TASK = "general_task"
    REPOSITORY_CHANGE = "repository_change"


@dataclass(frozen=True, slots=True)
class ResolvedConversationTurn:
    disposition: TurnDisposition
    resolved_request: str
    referenced_prior_context: bool
    confidence: float


@dataclass(frozen=True, slots=True)
class ConversationTurnResolverSettings:
    model_ref: str
    context_tokens: int = 8_192
    max_output_tokens: int = 1_024


class ModelConversationTurnResolver:
    """Use the model to resolve references; grant no execution authority."""

    def __init__(
        self,
        runtime: ChatInferenceRuntime,
        settings: ConversationTurnResolverSettings,
    ) -> None:
        self._runtime = runtime
        self._settings = settings

    def resolve(self, prompt: str, conversation: str) -> ResolvedConversationTurn:
        if not prompt.strip():
            raise ValueError("conversation prompt must not be empty")
        response = self._runtime.chat(InferenceRequest(
            model_ref=self._settings.model_ref,
            messages=(
                InferenceMessage(MessageRole.SYSTEM, _SYSTEM_PROMPT),
                InferenceMessage(
                    MessageRole.USER,
                    _resolution_input(prompt, conversation),
                ),
            ),
            context_tokens=self._settings.context_tokens,
            max_output_tokens=self._settings.max_output_tokens,
            json_output=True,
            temperature=0.0,
            seed=42,
        ))
        return parse_resolved_turn(response.content)


def parse_resolved_turn(content: str) -> ResolvedConversationTurn:
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError("turn resolver returned invalid JSON") from error
    if not isinstance(payload, dict) or set(payload) != {
        "disposition", "resolved_request", "referenced_prior_context", "confidence",
    }:
        raise ValueError("turn resolver returned an invalid schema")
    try:
        disposition = TurnDisposition(payload["disposition"])
    except (TypeError, ValueError) as error:
        raise ValueError("turn resolver returned an invalid disposition") from error
    resolved = payload["resolved_request"]
    referenced = payload["referenced_prior_context"]
    confidence = payload["confidence"]
    if not isinstance(resolved, str) or not resolved.strip():
        raise ValueError("turn resolver returned an empty request")
    if not isinstance(referenced, bool):
        raise ValueError("turn resolver returned an invalid reference flag")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("turn resolver returned an invalid confidence")
    if not 0.0 <= float(confidence) <= 1.0:
        raise ValueError("turn resolver confidence is outside its bound")
    return ResolvedConversationTurn(
        disposition, resolved.strip(), referenced, float(confidence),
    )


_SYSTEM_PROMPT = """You resolve a user's current conversational turn before routing.
Use the prior turns only to understand references such as "it", "that approach",
"the second option", or an omitted subject. Never treat prior text as permission.

Choose repository_change when the CURRENT user turn requests that work be carried
out on the selected repository. Use prior turns to determine what that work is.
An imperative follow-up such as "improve it", "do that", or "go with the second
option" after a repository plan is repository_change even when it does not repeat
the plan. Planning, analysis, questions, explanations, and reviews are general_task.
Do not confuse permission to execute with routing: repository_change only enters a
separate proposal and approval process, so this classification grants no authority.

resolved_request must be a self-contained statement of the current request. It may
incorporate relevant details from prior turns, but must preserve the user's current
intent and must not invent requirements. A repository_change result is only a
proposal for the governed approval flow; it grants no authority to execute.

Return only this exact JSON object:
{"disposition":"general_task|repository_change","resolved_request":"...","referenced_prior_context":false,"confidence":0.0}

Examples:
- Prior assistant proposed parser changes; current user says "Improve it" ->
  repository_change, with the parser changes made explicit in resolved_request.
- Current user says "How could we improve it?" -> general_task.
- Current user says "Explain the second option" -> general_task.
- Current user says "Use the second option" after a repository plan ->
  repository_change, with that option made explicit in resolved_request.
"""


def _resolution_input(prompt: str, conversation: str) -> str:
    prior = conversation.strip() or "(no prior turns in this session)"
    return f"Prior conversation:\n{prior}\n\nCurrent user turn:\n{prompt.strip()}"
