"""Core boundary for durable terminal-result retention and local learning."""

from __future__ import annotations

from typing import Protocol

from fam_os.core.contracts import TaskResult


class TerminalOutcomePort(Protocol):
    def result(self, request_id: str) -> TaskResult | None: ...

    def finalize(self, record, snapshot, result: TaskResult) -> bool: ...
