"""Console facade for model-driven conversational turn resolution."""

from __future__ import annotations


class ConsoleConversationTurnApi:
    def __init__(self, owner_id, memory, resolver) -> None:
        self._owner_id = owner_id
        self._memory = memory
        self._resolver = resolver

    def resolve(self, document: dict, session_id: str) -> dict:
        if not isinstance(document, dict) or set(document) != {"prompt"}:
            raise ValueError("conversation turn fields must match exactly")
        prompt = document["prompt"]
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("conversation prompt must be non-empty")
        context = self._memory.context_for_session(self._owner_id, session_id)
        result = self._resolver.resolve(prompt, context)
        return {
            "disposition": result.disposition.value,
            "resolved_request": result.resolved_request,
            "referenced_prior_context": result.referenced_prior_context,
            "confidence": result.confidence,
        }
