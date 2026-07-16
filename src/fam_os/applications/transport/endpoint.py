"""Private Unix-domain listener for authenticated Application Fabric sessions."""

import os
import socket
import stat
from dataclasses import dataclass
from pathlib import Path

from fam_os.applications.transport.connection import AuthenticatedLocalConnection


@dataclass(frozen=True, slots=True)
class UnixEndpointConfiguration:
    path: Path
    backlog: int = 16

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise ValueError("Unix endpoint path must be absolute")
        if self.backlog <= 0 or self.backlog > 128:
            raise ValueError("Unix endpoint backlog is invalid")


class UnixApplicationServer:
    def __init__(self, configuration, authorization, dispatcher):
        self.configuration = configuration
        self.authorization = authorization
        self.dispatcher = dispatcher
        self._listener = None

    def open(self) -> None:
        if self._listener is not None:
            return
        _require_private_parent(self.configuration.path.parent)
        if self.configuration.path.exists() or self.configuration.path.is_symlink():
            raise FileExistsError("Unix endpoint path already exists")
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
            raise RuntimeError("Unix application server is not open")
        stream, _address = self._listener.accept()
        connection = None
        try:
            connection = AuthenticatedLocalConnection.authenticate(
                stream, self.authorization, self.dispatcher
            )
            connected = getattr(self.dispatcher, "connected", None)
            if connected is not None:
                connected(connection)
            while connection.process_next():
                pass
        finally:
            if connection is not None:
                connection.close()
            else:
                stream.close()

    def close(self) -> None:
        if self._listener is not None:
            self._listener.close()
            self._listener = None
        _remove_owned_socket(self.configuration.path)


def _require_private_parent(path: Path) -> None:
    details = path.stat(follow_symlinks=False)
    if not stat.S_ISDIR(details.st_mode) or path.is_symlink():
        raise ValueError("Unix endpoint parent must be a real directory")
    if details.st_uid != os.geteuid():
        raise PermissionError("Unix endpoint parent must be owned by current user")
    if details.st_mode & 0o022:
        raise PermissionError("Unix endpoint parent cannot be group/world writable")


def _require_owned_socket(path: Path) -> None:
    details = path.stat(follow_symlinks=False)
    if not stat.S_ISSOCK(details.st_mode) or details.st_uid != os.geteuid():
        raise PermissionError("Unix endpoint must be an owned socket")
    if stat.S_IMODE(details.st_mode) != 0o600:
        raise PermissionError("Unix endpoint mode must be 0600")


def _remove_owned_socket(path: Path) -> None:
    try:
        details = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISSOCK(details.st_mode) and details.st_uid == os.geteuid():
        path.unlink()
