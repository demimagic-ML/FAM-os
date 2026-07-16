"""Core-client boundary used by every FAM Shell presentation."""

from typing import Protocol

from fam_os.shell.contracts import (
    ShellAskCommand,
    ShellCancelCommand,
    ShellDecisionCommand,
    ShellSessionSnapshot,
)


class ShellCoreClient(Protocol):
    def ask(self, command: ShellAskCommand) -> ShellSessionSnapshot: ...

    def snapshot(self, session_id: str) -> ShellSessionSnapshot: ...

    def decide(self, command: ShellDecisionCommand) -> ShellSessionSnapshot: ...

    def cancel(self, command: ShellCancelCommand) -> ShellSessionSnapshot: ...


class ShellCoreGateway(ShellCoreClient, Protocol):
    """Server-side implementation of the same narrow client surface."""
