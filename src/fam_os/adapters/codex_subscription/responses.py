"""Strict parser for effect-free ``codex exec --json`` events."""

from __future__ import annotations

from dataclasses import dataclass
import json

from .errors import CodexSubscriptionError


_PASSIVE_ITEM_TYPES = frozenset({"agent_message", "reasoning", "plan"})


@dataclass(frozen=True, slots=True)
class CodexTurnResult:
    content: str
    input_tokens: int
    output_tokens: int


def parse_effect_free_turn(payload: str) -> CodexTurnResult:
    messages: list[str] = []
    usage = None
    saw_turn = False
    for line in payload.splitlines():
        if not line.strip():
            continue
        event = _event(line)
        event_type = event.get("type")
        if event_type == "turn.started":
            saw_turn = True
        elif event_type in {"item.started", "item.updated", "item.completed"}:
            item = event.get("item")
            if not isinstance(item, dict):
                raise CodexSubscriptionError("codex_event_invalid")
            item_type = item.get("type")
            if item_type not in _PASSIVE_ITEM_TYPES:
                raise CodexSubscriptionError("codex_tool_activity_rejected")
            if event_type == "item.completed" and item_type == "agent_message":
                text = item.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise CodexSubscriptionError("codex_message_invalid")
                messages.append(text)
        elif event_type == "turn.completed":
            usage = _usage(event.get("usage"))
        elif event_type in {"thread.started"}:
            continue
        else:
            raise CodexSubscriptionError("codex_event_not_allowed")
    if not saw_turn or usage is None or not messages:
        raise CodexSubscriptionError("codex_turn_incomplete")
    return CodexTurnResult(messages[-1], *usage)


def _event(line: str) -> dict:
    try:
        value = json.loads(line)
    except json.JSONDecodeError as error:
        raise CodexSubscriptionError("codex_event_invalid") from error
    if not isinstance(value, dict):
        raise CodexSubscriptionError("codex_event_invalid")
    return value


def _usage(value) -> tuple[int, int]:
    if not isinstance(value, dict):
        raise CodexSubscriptionError("codex_usage_invalid")
    prompt = value.get("input_tokens")
    output = value.get("output_tokens")
    if (
        not isinstance(prompt, int) or isinstance(prompt, bool) or prompt < 0
        or not isinstance(output, int) or isinstance(output, bool) or output < 0
    ):
        raise CodexSubscriptionError("codex_usage_invalid")
    return prompt, output
