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
        if self.maximum_frame_bytes <= 0 or self.maximum_frame_bytes > 4_194_304:
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

    def snapshot(self, session_id):
        return self._exchange(
            ShellWireKind.SNAPSHOT_QUERY, ShellSnapshotQuery(session_id)
        )

    def decide(self, command):
        return self._exchange(ShellWireKind.DECIDE, command)

    def cancel(self, command):
        return self._exchange(ShellWireKind.CANCEL, command)

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
        return decode_snapshot(response)


def _require_owned_socket(path: Path) -> None:
    details = path.stat(follow_symlinks=False)
    if not stat.S_ISSOCK(details.st_mode) or path.is_symlink():
        raise PermissionError("shell endpoint must be a real Unix socket")
    if details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) != 0o600:
        raise PermissionError("shell endpoint owner or mode is invalid")
