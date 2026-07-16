"""Private peer-authenticated Unix listener for FAM Shell requests."""

import os
import socket
import stat
from dataclasses import dataclass
from pathlib import Path

from fam_os.applications.transport.auth import (
    PeerAuthorizationPolicy,
    unix_peer_credentials,
)
from fam_os.shell.wire import MAX_SHELL_FRAME_BYTES, receive_frame, send_frame


@dataclass(frozen=True, slots=True)
class UnixShellServerConfiguration:
    path: Path
    backlog: int = 16
    maximum_frame_bytes: int = MAX_SHELL_FRAME_BYTES

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise ValueError("shell server path must be absolute")
        if self.backlog <= 0 or self.backlog > 128:
            raise ValueError("shell server backlog is invalid")
        if self.maximum_frame_bytes <= 0 or self.maximum_frame_bytes > 4_194_304:
            raise ValueError("shell frame limit is invalid")


class UnixShellServer:
    def __init__(self, configuration, authorization, dispatcher):
        if not isinstance(authorization, PeerAuthorizationPolicy):
            raise ValueError("shell server requires peer authorization")
        self.configuration = configuration
        self.authorization = authorization
        self.dispatcher = dispatcher
        self._listener = None

    def open(self) -> None:
        if self._listener is not None:
            return
        _require_private_parent(self.configuration.path.parent)
        if self.configuration.path.exists() or self.configuration.path.is_symlink():
            raise FileExistsError("shell endpoint already exists")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(self.configuration.path))
            os.chmod(self.configuration.path, 0o600)
            listener.listen(self.configuration.backlog)
            _require_owned_socket(self.configuration.path)
        except Exception:
            listener.close()
            _remove_owned_socket(self.configuration.path)
            raise
        self._listener = listener

    def serve_once(self) -> None:
        if self._listener is None:
            raise RuntimeError("shell server is not open")
        stream, _address = self._listener.accept()
        try:
            if not self.authorization.authorize(unix_peer_credentials(stream)):
                raise PermissionError("shell peer is not authorized")
            request = receive_frame(stream, self.configuration.maximum_frame_bytes)
            response = self.dispatcher.dispatch(request)
            send_frame(stream, response, self.configuration.maximum_frame_bytes)
        finally:
            stream.close()

    def close(self) -> None:
        if self._listener is not None:
            self._listener.close()
            self._listener = None
        _remove_owned_socket(self.configuration.path)


def _require_private_parent(path: Path) -> None:
    details = path.stat(follow_symlinks=False)
    if not stat.S_ISDIR(details.st_mode) or path.is_symlink():
        raise ValueError("shell endpoint parent must be a real directory")
    if details.st_uid != os.geteuid() or details.st_mode & 0o022:
        raise PermissionError("shell endpoint parent must be private and owned")


def _require_owned_socket(path: Path) -> None:
    details = path.stat(follow_symlinks=False)
    if not stat.S_ISSOCK(details.st_mode) or details.st_uid != os.geteuid():
        raise PermissionError("shell endpoint must be an owned socket")
    if stat.S_IMODE(details.st_mode) != 0o600:
        raise PermissionError("shell endpoint mode must be 0600")


def _remove_owned_socket(path: Path) -> None:
    try:
        details = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISSOCK(details.st_mode) and details.st_uid == os.geteuid():
        path.unlink()
