"""Bounded request transport over mutually authenticated TLS 1.3."""

from __future__ import annotations

import socket
import struct
from collections.abc import Callable
from dataclasses import dataclass

from fam_os.fabric.pairing import PeerEndpoint
from fam_os.fabric.tls_trust import AuthenticatedPeer, PairedPeerTrust

MAX_PEER_FRAME_BYTES = 1024 * 1024
MAX_PEER_IO_TIMEOUT_SECONDS = 360.0


@dataclass(frozen=True, slots=True)
class PeerTlsServerSettings:
    listen_host: str
    listen_port: int
    backlog: int = 16
    accept_timeout_seconds: float = 0.5
    io_timeout_seconds: float = 10.0
    max_frame_bytes: int = MAX_PEER_FRAME_BYTES

    def __post_init__(self) -> None:
        if (
            not 1 <= len(self.listen_host) <= 253
            or any(character.isspace() or ord(character) < 33 for character in self.listen_host)
            or not 0 <= self.listen_port <= 65535
            or not 1 <= self.backlog <= 128
            or not 0.05 <= self.accept_timeout_seconds <= 10
            or not 0.1 <= self.io_timeout_seconds <= MAX_PEER_IO_TIMEOUT_SECONDS
            or not 1024 <= self.max_frame_bytes <= MAX_PEER_FRAME_BYTES
        ):
            raise ValueError("peer TLS server settings are invalid")


class MutualTlsPeerServer:
    def __init__(
        self,
        settings: PeerTlsServerSettings,
        trust: PairedPeerTrust,
        handler: Callable[[AuthenticatedPeer, bytes], bytes],
    ) -> None:
        self.settings = settings
        self._trust = trust
        self._handler = handler
        self._context = trust.server_context()
        self._socket: socket.socket | None = None

    @property
    def address(self) -> PeerEndpoint:
        if self._socket is None:
            raise RuntimeError("peer TLS server is not open")
        address = self._socket.getsockname()
        return PeerEndpoint(str(address[0]), int(address[1]))

    def open(self) -> None:
        if self._socket is not None:
            return
        addresses = socket.getaddrinfo(
            self.settings.listen_host, self.settings.listen_port, type=socket.SOCK_STREAM,
            flags=socket.AI_PASSIVE,
        )
        if not addresses:
            raise OSError("peer TLS listen address could not be resolved")
        family, kind, protocol, _, address = addresses[0]
        listener = socket.socket(family, kind, protocol)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(address)
            listener.listen(self.settings.backlog)
            listener.settimeout(self.settings.accept_timeout_seconds)
        except BaseException:
            listener.close()
            raise
        self._socket = listener

    def serve_once(self) -> AuthenticatedPeer:
        listener = self._socket
        if listener is None:
            raise RuntimeError("peer TLS server is not open")
        connection, _ = listener.accept()
        with connection:
            connection.settimeout(self.settings.io_timeout_seconds)
            with self._context.wrap_socket(connection, server_side=True) as secured:
                peer = self._trust.authenticate(secured)
                request = read_frame(secured, self.settings.max_frame_bytes)
                response = self._handler(peer, request)
                write_frame(secured, response, self.settings.max_frame_bytes)
                return peer

    def close(self) -> None:
        listener, self._socket = self._socket, None
        if listener is not None:
            listener.close()


class MutualTlsPeerClient:
    def __init__(
        self,
        trust: PairedPeerTrust,
        *,
        connect_timeout_seconds: float = 5.0,
        io_timeout_seconds: float = 10.0,
        max_frame_bytes: int = MAX_PEER_FRAME_BYTES,
    ) -> None:
        if (
            not 0.1 <= connect_timeout_seconds <= 30
            or not 0.1 <= io_timeout_seconds <= MAX_PEER_IO_TIMEOUT_SECONDS
            or not 1024 <= max_frame_bytes <= MAX_PEER_FRAME_BYTES
        ):
            raise ValueError("peer TLS client settings are invalid")
        self._trust = trust
        self._context = trust.client_context()
        self._connect_timeout = connect_timeout_seconds
        self._io_timeout = io_timeout_seconds
        self._max_frame = max_frame_bytes

    def request(self, device_id: str, payload: bytes) -> tuple[AuthenticatedPeer, bytes]:
        approval = self._trust.approval(device_id)
        endpoint = approval.peer_endpoint
        with socket.create_connection(
            (endpoint.host, endpoint.port), timeout=self._connect_timeout,
        ) as connection:
            connection.settimeout(self._io_timeout)
            with self._context.wrap_socket(connection) as secured:
                peer = self._trust.authenticate(secured, expected_device_id=device_id)
                write_frame(secured, payload, self._max_frame)
                return peer, read_frame(secured, self._max_frame)


def write_frame(connection: socket.socket, payload: bytes, maximum: int) -> None:
    if not 1 <= len(payload) <= maximum:
        raise ValueError("peer TLS frame size is invalid")
    connection.sendall(struct.pack("!I", len(payload)) + payload)


def read_frame(connection: socket.socket, maximum: int) -> bytes:
    size = struct.unpack("!I", _read_exact(connection, 4))[0]
    if not 1 <= size <= maximum:
        raise ValueError("peer TLS frame size is invalid")
    return _read_exact(connection, size)


def _read_exact(connection: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise ConnectionError("peer TLS connection closed before a complete frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
