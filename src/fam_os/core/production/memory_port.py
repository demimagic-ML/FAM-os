"""Core-facing port for volatile conversation memory."""

from typing import Protocol


class SessionMemoryPort(Protocol):
    def begin_request(
        self, request_id: str, owner_id: str, session_id: str, prompt: str,
    ) -> None: ...

    def context_for_request(self, request_id: str) -> str: ...

    def record_assistant(
        self, request_id: str, content: str, assurance: str,
    ) -> None: ...

