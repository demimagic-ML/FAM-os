"""Peer-authenticated one-request Unix service for network enforcement."""

import os
from pathlib import Path
import socket
import struct

from fam_os.core.engineering.integration_network import (
    IntegrationNetworkEnforcementRequest, IntegrationNetworkLease,
)
from fam_os.schemas import dumps_document, loads_document


class UnixIntegrationNetworkBrokerServer:
    def __init__(
        self, path: Path, *, socket_owner_uid: int, socket_group_id: int,
        allowed_peer_uid: int, allowed_peer_cgroup: str, handler,
        maximum_message_bytes: int = 1_048_576,
    ) -> None:
        if not path.is_absolute() or min(
            socket_owner_uid, socket_group_id, allowed_peer_uid,
        ) < 0:
            raise ValueError("network broker Unix configuration is invalid")
        if maximum_message_bytes <= 0:
            raise ValueError("network broker message bound must be positive")
        if (
            not allowed_peer_cgroup.startswith("/")
            or ".." in allowed_peer_cgroup.split("/")
            or "\n" in allowed_peer_cgroup
        ):
            raise ValueError("network broker peer cgroup is invalid")
        self.path = path
        self._owner = socket_owner_uid
        self._group = socket_group_id
        self._peer = allowed_peer_uid
        self._peer_cgroup = allowed_peer_cgroup
        self._handler = handler
        self._limit = maximum_message_bytes
        self._listener = None

    def open(self) -> None:
        _require_parent(self.path.parent, self._owner)
        _remove_owned_socket(self.path, self._owner)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(self.path))
            os.chown(self.path, self._owner, self._group)
            os.chmod(self.path, 0o660)
            listener.listen(16)
            listener.settimeout(1)
        except BaseException:
            listener.close()
            _remove_owned_socket(self.path, self._owner)
            raise
        self._listener = listener

    def serve_once(self) -> None:
        if self._listener is None:
            raise RuntimeError("network broker server is not open")
        stream, _address = self._listener.accept()
        try:
            if not _peer_allowed(stream, self._peer, self._peer_cgroup):
                return
            operation, value = self._receive(stream)
            result = self._dispatch(operation, value)
            response = (dumps_document(result) + "\n").encode()
            if len(response) > self._limit:
                raise ValueError("network broker response exceeds bound")
            stream.sendall(response)
        finally:
            stream.close()

    def close(self) -> None:
        listener, self._listener = self._listener, None
        if listener is not None:
            listener.close()
        _remove_owned_socket(self.path, self._owner)

    def _receive(self, stream):
        request = bytearray()
        while len(request) <= self._limit:
            part = stream.recv(min(65_536, self._limit + 1 - len(request)))
            if not part:
                break
            request.extend(part)
        if len(request) > self._limit:
            raise ValueError("network broker request exceeds bound")
        try:
            operation, document = bytes(request).decode("utf-8").split("\n", 1)
        except (UnicodeDecodeError, ValueError) as error:
            raise ValueError("network broker request framing is invalid") from error
        if not document.endswith("\n") or "\n" in document[:-1]:
            raise ValueError("network broker request must contain one document")
        return operation, loads_document(document[:-1])

    def _dispatch(self, operation, value):
        if operation == "open" and isinstance(value, IntegrationNetworkEnforcementRequest):
            return self._handler.open(value)
        if operation == "recover" and isinstance(value, IntegrationNetworkEnforcementRequest):
            return self._handler.recover(value)
        if operation == "observe" and isinstance(value, IntegrationNetworkLease):
            return self._handler.observe(value)
        if operation == "close" and isinstance(value, IntegrationNetworkLease):
            return self._handler.close(value)
        raise ValueError("network broker operation or contract is invalid")


def _require_parent(path: Path, owner_uid: int) -> None:
    details = path.stat(follow_symlinks=False)
    if path.is_symlink() or not path.is_dir() or details.st_uid != owner_uid:
        raise PermissionError("network broker socket parent ownership is invalid")
    if details.st_mode & 0o022:
        raise PermissionError("network broker socket parent is group/world writable")


def _remove_owned_socket(path: Path, owner_uid: int) -> None:
    if not path.exists() and not path.is_symlink():
        return
    details = path.lstat()
    if not path.is_socket() or details.st_uid != owner_uid:
        raise PermissionError("refusing to replace unowned network broker endpoint")
    path.unlink()


def _peer_allowed(stream, allowed_uid: int, allowed_cgroup: str) -> bool:
    if not hasattr(socket, "SO_PEERCRED"):
        raise RuntimeError("Unix peer credentials are unavailable")
    size = struct.calcsize("3i")
    raw = stream.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size)
    pid, uid, _gid = struct.unpack("3i", raw)
    if uid != allowed_uid:
        return False
    descriptor = os.open(
        f"/proc/{pid}", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        cgroup = os.open("cgroup", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor)
        try:
            raw_cgroup = os.read(cgroup, 4097)
        finally:
            os.close(cgroup)
    finally:
        os.close(descriptor)
    if len(raw_cgroup) > 4096:
        raise ValueError("network broker peer cgroup exceeds bound")
    lines = raw_cgroup.decode("utf-8").splitlines()
    paths = tuple(line[3:] for line in lines if line.startswith("0::"))
    return paths == (allowed_cgroup,)
