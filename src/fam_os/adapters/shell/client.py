"""Unix-domain Core client used by the unprivileged FAM Shell process."""

import os
import socket
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fam_os.shell import ShellSnapshotQuery
from fam_os.shell.wire import (
    MAX_SHELL_FRAME_BYTES,
    ShellWireKind,
    decode_adaptation_response,
    decode_engineering_response,
    decode_integration_environment_response,
    decode_engineering_secret_response,
    decode_engineering_loop_response,
    decode_memory_response,
    decode_peer_response,
    decode_snapshot,
    receive_frame,
    request_message,
    send_frame,
)


def _identifier() -> str:
    return str(uuid4())


@dataclass(frozen=True, slots=True)
class UnixShellClientConfiguration:
    path: Path
    timeout_seconds: float = 10.0
    maximum_frame_bytes: int = MAX_SHELL_FRAME_BYTES

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise ValueError("shell endpoint path must be absolute")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 120:
            raise ValueError("shell endpoint timeout is invalid")
        if self.maximum_frame_bytes <= 0 or self.maximum_frame_bytes > MAX_SHELL_FRAME_BYTES:
            raise ValueError("shell frame limit is invalid")


class UnixShellCoreClient:
    def __init__(
        self, configuration: UnixShellClientConfiguration,
        message_id_factory: Callable[[], str] = _identifier,
    ):
        self._configuration = configuration
        self._message_id_factory = message_id_factory

    def ask(self, command):
        return self._exchange(ShellWireKind.ASK, command)

    def ask_verified(self, command):
        return self._exchange(ShellWireKind.VERIFIED_ASK, command)

    def snapshot(self, session_id):
        return self._exchange(
            ShellWireKind.SNAPSHOT_QUERY, ShellSnapshotQuery(session_id)
        )

    def decide(self, command):
        return self._exchange(ShellWireKind.DECIDE, command)

    def cancel(self, command):
        return self._exchange(ShellWireKind.CANCEL, command)

    def memory_query(self, command):
        return self._exchange(ShellWireKind.MEMORY_QUERY, command)

    def memory_correct(self, command):
        return self._exchange(ShellWireKind.MEMORY_CORRECT, command)

    def memory_expire(self, command):
        return self._exchange(ShellWireKind.MEMORY_EXPIRE, command)

    def memory_delete(self, command):
        return self._exchange(ShellWireKind.MEMORY_DELETE, command)

    def adaptation_query(self, command):
        return self._exchange(ShellWireKind.ADAPTATION_QUERY, command)

    def adaptation_control(self, command):
        return self._exchange(ShellWireKind.ADAPTATION_CONTROL, command)

    def peer_query(self, command):
        return self._exchange(ShellWireKind.PEER_QUERY, command)

    def peer_probe(self, command):
        return self._exchange(ShellWireKind.PEER_PROBE, command)

    def peer_control(self, command):
        return self._exchange(ShellWireKind.PEER_CONTROL, command)

    def peer_context(self, command):
        return self._exchange(ShellWireKind.PEER_CONTEXT, command)

    def engineering_context(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_CONTEXT, command)

    def engineering_activate(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_ACTIVATE, command)

    def engineering_query(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_QUERY, command)

    def engineering_revoke(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_REVOKE, command)

    def integration_environment_start(self, command):
        return self._exchange(ShellWireKind.INTEGRATION_ENVIRONMENT_START, command)

    def integration_environment_query(self, command):
        return self._exchange(ShellWireKind.INTEGRATION_ENVIRONMENT_QUERY, command)

    def integration_environment_control(self, command):
        return self._exchange(ShellWireKind.INTEGRATION_ENVIRONMENT_CONTROL, command)

    def engineering_secret_query(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_SECRET_QUERY, command)

    def engineering_secret_mutation(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_SECRET_MUTATION, command)

    def engineering_loop_start(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_LOOP_START, command)

    def engineering_loop_query(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_LOOP_QUERY, command)

    def engineering_loop_mutation(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_LOOP_MUTATION, command)

    def engineering_candidate_edit(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_CANDIDATE_EDIT, command)

    def engineering_candidate_verify(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_CANDIDATE_VERIFY, command)

    def engineering_candidate_reverify(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_CANDIDATE_REVERIFY, command)

    def engineering_changeset_preview(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_CHANGESET_PREVIEW, command)

    def engineering_changeset_apply(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_CHANGESET_APPLY, command)

    def engineering_publication(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_PUBLICATION, command)

    def engineering_incident_advance(self, command):
        return self._exchange(ShellWireKind.ENGINEERING_INCIDENT_ADVANCE, command)

    def _exchange(self, kind, value):
        _require_owned_socket(self._configuration.path)
        message = request_message(self._message_id_factory(), kind, value)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.settimeout(self._configuration.timeout_seconds)
            stream.connect(str(self._configuration.path))
            send_frame(stream, message, self._configuration.maximum_frame_bytes)
            response = receive_frame(stream, self._configuration.maximum_frame_bytes)
        if response.correlation_id != message.message_id:
            raise RuntimeError("shell response correlation is invalid")
        if response.kind is ShellWireKind.ERROR:
            code = response.payload.get("code")
            if not isinstance(code, str):
                raise RuntimeError("shell Core returned an invalid error")
            raise RuntimeError(code)
        if response.kind is ShellWireKind.MEMORY_RESPONSE:
            return decode_memory_response(response)
        if response.kind is ShellWireKind.ADAPTATION_RESPONSE:
            return decode_adaptation_response(response)
        if response.kind is ShellWireKind.PEER_RESPONSE:
            return decode_peer_response(response)
        if response.kind is ShellWireKind.ENGINEERING_RESPONSE:
            return decode_engineering_response(response)
        if response.kind is ShellWireKind.INTEGRATION_ENVIRONMENT_RESPONSE:
            return decode_integration_environment_response(response)
        if response.kind is ShellWireKind.ENGINEERING_SECRET_RESPONSE:
            return decode_engineering_secret_response(response)
        if response.kind is ShellWireKind.ENGINEERING_LOOP_RESPONSE:
            return decode_engineering_loop_response(response)
        return decode_snapshot(response)


def _require_owned_socket(path: Path) -> None:
    details = path.stat(follow_symlinks=False)
    if not stat.S_ISSOCK(details.st_mode) or path.is_symlink():
        raise PermissionError("shell endpoint must be a real Unix socket")
    if details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) != 0o600:
        raise PermissionError("shell endpoint owner or mode is invalid")
