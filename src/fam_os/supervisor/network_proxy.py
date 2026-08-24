"""Deterministic CONNECT-only allowlist proxy with pre-forward byte quota."""

from dataclasses import dataclass
import ipaddress
import selectors
import socket
from threading import Lock
from typing import Callable

from fam_os.supervisor.network_contracts import split_network_endpoint


_MAX_HEADER_BYTES = 16_384


@dataclass(frozen=True, slots=True)
class ProxyUsage:
    destinations: tuple[str, ...]
    transmitted_bytes: int
    received_bytes: int
    quota_exceeded: bool


class NetworkByteQuota:
    def __init__(self, maximum_bytes: int, observer: Callable[[ProxyUsage], None]):
        if maximum_bytes <= 0:
            raise ValueError("proxy byte quota must be positive")
        self._maximum = maximum_bytes
        self._observer = observer
        self._lock = Lock()
        self._sent = self._received = 0
        self._destinations = []
        self._exceeded = False

    def record_destination(self, destination: str) -> None:
        with self._lock:
            if destination not in self._destinations:
                self._destinations.append(destination)
            snapshot = self._snapshot()
        self._observer(snapshot)

    def consume(self, requested: int, *, transmitted: bool) -> int:
        with self._lock:
            remaining = self._maximum - self._sent - self._received
            permitted = min(requested, max(0, remaining))
            if transmitted:
                self._sent += permitted
            else:
                self._received += permitted
            if permitted < requested:
                self._exceeded = True
            snapshot = self._snapshot()
        self._observer(snapshot)
        return permitted

    def snapshot(self) -> ProxyUsage:
        with self._lock:
            return self._snapshot()

    def at_limit(self) -> bool:
        with self._lock:
            return self._sent + self._received >= self._maximum

    def _snapshot(self) -> ProxyUsage:
        return ProxyUsage(
            tuple(self._destinations), self._sent, self._received, self._exceeded,
        )


class BoundedConnectProxySession:
    def __init__(
        self, destinations, quota, *, resolver=None, dialer=None,
        active=lambda: True,
    ):
        self._destinations = frozenset(destinations)
        if not self._destinations:
            raise ValueError("proxy requires exact destinations")
        for destination in self._destinations:
            split_network_endpoint(destination)
        self._quota = quota
        self._resolver = resolver or socket.getaddrinfo
        self._dialer = dialer or socket.create_connection
        self._active = active

    def serve(self, client) -> None:
        header = _read_header(client)
        destination = _connect_destination(header)
        if destination not in self._destinations:
            _deny(client, b"403 Forbidden")
            raise PermissionError("CONNECT destination is outside allowlist")
        host, port = split_network_endpoint(destination)
        addresses = self._resolve(host, port)
        if not addresses:
            _deny(client, b"502 Bad Gateway")
            raise OSError("CONNECT destination has no permitted address")
        remote = self._dialer((addresses[0], port), timeout=10)
        try:
            self._quota.record_destination(destination)
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self._relay(client, remote)
        finally:
            remote.close()

    def _resolve(self, host, port):
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            values = self._resolver(host, port, type=socket.SOCK_STREAM)
            addresses = []
            for item in values:
                address = ipaddress.ip_address(item[4][0])
                if address.is_global and str(address) not in addresses:
                    addresses.append(str(address))
            return tuple(addresses)
        return (str(literal),)

    def _relay(self, client, remote):
        selector = selectors.DefaultSelector()
        selector.register(client, selectors.EVENT_READ, (remote, True))
        selector.register(remote, selectors.EVENT_READ, (client, False))
        try:
            while True:
                if not self._active():
                    return
                events = selector.select(timeout=1)
                if not events:
                    continue
                for key, _mask in events:
                    target, transmitted = key.data
                    chunk = key.fileobj.recv(65_536)
                    if not chunk:
                        return
                    permitted = self._quota.consume(
                        len(chunk), transmitted=transmitted,
                    )
                    if permitted:
                        target.sendall(chunk[:permitted])
                    if permitted < len(chunk) or self._quota.at_limit():
                        return
        finally:
            selector.close()


def _read_header(client) -> bytes:
    value = bytearray()
    while b"\r\n\r\n" not in value:
        part = client.recv(min(4096, _MAX_HEADER_BYTES + 1 - len(value)))
        if not part:
            raise ConnectionError("proxy client closed before CONNECT")
        value.extend(part)
        if len(value) > _MAX_HEADER_BYTES:
            _deny(client, b"431 Request Header Fields Too Large")
            raise ValueError("CONNECT header exceeds bound")
    header, trailing = bytes(value).split(b"\r\n\r\n", 1)
    if trailing:
        raise ValueError("CONNECT request cannot pipeline tunnel bytes")
    return header


def _connect_destination(header: bytes) -> str:
    try:
        lines = header.decode("ascii").split("\r\n")
        method, destination, version = lines[0].split(" ")
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("CONNECT request line is invalid") from error
    if method != "CONNECT" or version != "HTTP/1.1":
        raise ValueError("proxy accepts only HTTP/1.1 CONNECT")
    split_network_endpoint(destination)
    if any(line.lower().startswith("proxy-authorization:") for line in lines[1:]):
        raise ValueError("proxy credentials are forbidden")
    return destination


def _deny(client, status: bytes) -> None:
    client.sendall(b"HTTP/1.1 " + status + b"\r\nConnection: close\r\n\r\n")
