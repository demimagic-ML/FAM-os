"""Bounded loopback-only Chrome DevTools HTTP and WebSocket client."""

import base64
import hashlib
import json
import os
import socket
import struct
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler


class BoundedDevToolsClient:
    def __init__(self, port: int, *, timeout_seconds=5, maximum_bytes=8_388_608):
        if not 1 <= port <= 65535 or not 0 < timeout_seconds <= 30 or maximum_bytes <= 0:
            raise ValueError("DevTools client bounds are invalid")
        self._port = port
        self._timeout = timeout_seconds
        self._maximum = maximum_bytes
        self._next_id = 0

    def targets(self) -> tuple[dict, ...]:
        with build_opener(ProxyHandler({})).open(
            f"http://127.0.0.1:{self._port}/json/list", timeout=self._timeout,
        ) as response:
            content = response.read(self._maximum + 1)
        if len(content) > self._maximum:
            raise RuntimeError("DevTools target response exceeded its bound")
        values = json.loads(content.decode("utf-8", "strict"))
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise RuntimeError("DevTools target response is invalid")
        return tuple(values)

    def evaluate(self, expression: str):
        if not expression or len(expression.encode()) > 65_536:
            raise ValueError("DevTools expression is invalid")
        result = self._command("Runtime.evaluate", {
            "expression": expression, "returnByValue": True,
            "awaitPromise": True,
        })
        remote = result.get("result")
        if not isinstance(remote, dict) or "exceptionDetails" in result:
            raise RuntimeError("DevTools evaluation failed")
        return remote.get("value")

    def screenshot_png(self) -> bytes:
        self._command("Page.enable", {})
        result = self._command("Page.captureScreenshot", {
            "format": "png", "fromSurface": True, "captureBeyondViewport": False,
        })
        encoded = result.get("data")
        if not isinstance(encoded, str) or len(encoded) > 2 * self._maximum:
            raise RuntimeError("DevTools screenshot response is invalid")
        try:
            content = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise RuntimeError("DevTools screenshot is not strict base64") from error
        if not content.startswith(b"\x89PNG\r\n\x1a\n") or len(content) > self._maximum:
            raise RuntimeError("DevTools screenshot is not a bounded PNG")
        return content

    def _command(self, method, parameters):
        target = next((
            item for item in self.targets()
            if item.get("type") == "page" and isinstance(item.get("webSocketDebuggerUrl"), str)
        ), None)
        if target is None:
            raise RuntimeError("DevTools has no controllable page target")
        self._next_id += 1
        request_id = self._next_id
        payload = json.dumps({
            "id": request_id, "method": method, "params": parameters,
        }, separators=(",", ":")).encode()
        with self._connect(target["webSocketDebuggerUrl"]) as stream:
            _send_frame(stream, 1, payload)
            while True:
                opcode, content = _receive_message(stream, self._maximum)
                if opcode == 8:
                    raise RuntimeError("DevTools closed before response")
                if opcode != 1:
                    continue
                value = json.loads(content.decode("utf-8", "strict"))
                if not isinstance(value, dict) or value.get("id") != request_id:
                    continue
                if "error" in value or not isinstance(value.get("result"), dict):
                    raise RuntimeError("DevTools command was rejected")
                return value["result"]

    def _connect(self, url):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "ws" or parsed.hostname != "127.0.0.1"
            or parsed.port != self._port or not parsed.path.startswith("/devtools/")
            or parsed.query or parsed.fragment
        ):
            raise PermissionError("DevTools target escaped exact loopback endpoint")
        stream = socket.create_connection(("127.0.0.1", self._port), self._timeout)
        stream.settimeout(self._timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {parsed.path} HTTP/1.1\r\nHost: 127.0.0.1:{self._port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode()
        stream.sendall(request)
        header = _read_header(stream, 16_384)
        expected = base64.b64encode(hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
        ).digest()).decode()
        text = header.decode("iso-8859-1")
        if not text.startswith("HTTP/1.1 101 ") or f"Sec-WebSocket-Accept: {expected}".lower() not in text.lower():
            stream.close()
            raise RuntimeError("DevTools WebSocket handshake failed")
        return stream


def _send_frame(stream, opcode, payload):
    mask = os.urandom(4)
    size = len(payload)
    header = bytearray((0x80 | opcode,))
    header.extend((0x80 | size,) if size < 126 else (
        (0x80 | 126, *struct.pack("!H", size)) if size <= 65535
        else (0x80 | 127, *struct.pack("!Q", size))
    ))
    header.extend(mask)
    stream.sendall(bytes(header) + bytes(value ^ mask[index % 4] for index, value in enumerate(payload)))


def _receive_message(stream, maximum):
    fragments = bytearray(); initial = None
    while True:
        first, second = _read_exact(stream, 2)
        final, opcode, masked = bool(first & 0x80), first & 0x0F, bool(second & 0x80)
        size = second & 0x7F
        if size == 126: size = struct.unpack("!H", _read_exact(stream, 2))[0]
        elif size == 127: size = struct.unpack("!Q", _read_exact(stream, 8))[0]
        if masked or size + len(fragments) > maximum:
            raise RuntimeError("DevTools WebSocket frame is invalid or oversized")
        content = _read_exact(stream, size)
        if opcode == 9:
            _send_frame(stream, 10, content); continue
        if opcode in {1, 2, 8}: initial = opcode
        elif opcode != 0: continue
        fragments.extend(content)
        if final: return initial, bytes(fragments)


def _read_header(stream, maximum):
    value = bytearray()
    while not value.endswith(b"\r\n\r\n"):
        value.extend(_read_exact(stream, 1))
        if len(value) > maximum: raise RuntimeError("DevTools handshake exceeded its bound")
    return bytes(value)


def _read_exact(stream, size):
    value = bytearray()
    while len(value) < size:
        chunk = stream.recv(size - len(value))
        if not chunk: raise EOFError("DevTools transport closed")
        value.extend(chunk)
    return bytes(value)
