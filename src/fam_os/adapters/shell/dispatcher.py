"""Content-safe server dispatch from Shell wire requests to a Core gateway."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from fam_os.shell.contracts import ShellSessionSnapshot
from fam_os.shell.ports import ShellCoreGateway
from fam_os.shell.wire import (
    ShellWireKind,
    decode_request,
    error_message,
    snapshot_message,
)


def _identifier() -> str:
    return str(uuid4())


@dataclass(slots=True)
class ShellRequestDispatcher:
    gateway: ShellCoreGateway
    message_id_factory: Callable[[], str] = _identifier

    def dispatch(self, message):
        try:
            command = decode_request(message)
        except Exception:
            return self._error(message, "shell.request_invalid")
        try:
            snapshot = self._invoke(message.kind, command)
        except Exception:
            return self._error(message, "shell.core_unavailable")
        if not isinstance(snapshot, ShellSessionSnapshot):
            return self._error(message, "shell.response_invalid")
        if not _identity_matches(message.kind, command, snapshot):
            return self._error(message, "shell.response_invalid")
        return snapshot_message(
            self.message_id_factory(), message.message_id, snapshot
        )

    def _invoke(self, kind, command):
        if kind is ShellWireKind.ASK:
            return self.gateway.ask(command)
        if kind is ShellWireKind.SNAPSHOT_QUERY:
            return self.gateway.snapshot(command.session_id)
        if kind is ShellWireKind.DECIDE:
            return self.gateway.decide(command)
        if kind is ShellWireKind.CANCEL:
            return self.gateway.cancel(command)
        raise ValueError("unsupported shell request")

    def _error(self, message, code):
        return error_message(
            self.message_id_factory(), message.message_id, code
        )


def _identity_matches(kind, command, snapshot) -> bool:
    if kind is ShellWireKind.ASK:
        return snapshot.request_id == command.request_id
    return snapshot.session_id == command.session_id
