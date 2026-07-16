"""Thin Shell controller; all task and authority policy stays in Core."""

from collections.abc import Callable
from uuid import uuid4

from fam_os.shell.contracts import (
    ShellAskCommand,
    ShellCancelCommand,
    ShellContext,
    ShellDecision,
    ShellDecisionCommand,
    ShellRunState,
)
from fam_os.shell.state import accept_snapshot


def _identifier() -> str:
    return str(uuid4())


class ShellController:
    def __init__(self, client, request_id_factory: Callable[[], str] = _identifier):
        self._client = client
        self._request_id_factory = request_id_factory
        self._contexts = {}
        self._snapshot = None

    @property
    def snapshot(self):
        return self._snapshot

    def contexts(self):
        return tuple(self._contexts.values())

    def add_context(self, context: ShellContext) -> None:
        self._require_context_mutable()
        if context.context_id in self._contexts:
            raise ValueError("shell context already exists")
        self._contexts[context.context_id] = context

    def remove_context(self, context_id: str) -> None:
        self._require_context_mutable()
        if self._contexts.pop(context_id, None) is None:
            raise KeyError("shell context does not exist")

    def ask(self, prompt: str, verification_required=False):
        if self._snapshot is not None and self._snapshot.state is not ShellRunState.TERMINAL:
            raise RuntimeError("a shell request is already active")
        capabilities = tuple(dict.fromkeys(
            capability
            for context in self.contexts()
            for capability in context.capability_ids
        ))
        command = ShellAskCommand(
            self._request_id_factory(), prompt, self.contexts(), capabilities,
            verification_required,
        )
        incoming = self._client.ask(command)
        if incoming.request_id != command.request_id:
            raise ValueError("Core returned the wrong shell request")
        self._snapshot = accept_snapshot(None, incoming)
        return self._snapshot

    def refresh(self):
        current = self._require_snapshot()
        incoming = self._client.snapshot(current.session_id)
        self._snapshot = accept_snapshot(current, incoming)
        return self._snapshot

    def decide(self, decision: ShellDecision):
        current = self._require_snapshot()
        if current.approval is None:
            raise RuntimeError("shell request is not waiting for approval")
        command = ShellDecisionCommand(
            current.session_id, current.revision,
            current.approval.approval_id, decision,
        )
        self._snapshot = accept_snapshot(current, self._client.decide(command))
        return self._snapshot

    def cancel(self):
        current = self._require_snapshot()
        command = ShellCancelCommand(current.session_id, current.revision)
        self._snapshot = accept_snapshot(current, self._client.cancel(command))
        return self._snapshot

    def _require_snapshot(self):
        if self._snapshot is None:
            raise RuntimeError("shell has no active request")
        return self._snapshot

    def _require_context_mutable(self):
        if self._snapshot is not None and self._snapshot.state is not ShellRunState.TERMINAL:
            raise RuntimeError("context is frozen while a shell request is active")
