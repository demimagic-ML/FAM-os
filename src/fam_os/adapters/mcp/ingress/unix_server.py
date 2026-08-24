"""Owner-private Unix endpoint for authenticated MCP ingress sessions."""

from __future__ import annotations

import asyncio
import os
import socket
import struct
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock, Thread, current_thread
from uuid import uuid4

from fam_os.adapters.mcp.ingress.auth import OneTimeMcpIngressTokens
from fam_os.adapters.mcp.ingress.engine import AuthenticatedMcpIngress
from fam_os.adapters.mcp.ingress.unix_wire import (
    McpIngressWireKind,
    McpIngressWireMessage,
    receive_mcp_ingress_frame,
    send_mcp_ingress_frame,
)


class UnixMcpIngressServer:
    def __init__(self, path: Path, owner_uid: int, identities, gateway) -> None:
        self.path = path
        self._owner_uid = owner_uid
        self._identities = identities
        self._gateway = gateway
        self._tokens = OneTimeMcpIngressTokens()
        self._listener: socket.socket | None = None
        self._clients: set[socket.socket] = set()
        self._threads: set[Thread] = set()
        self._lock = Lock()

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _remove_owned_socket(self.path, self._owner_uid)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(self.path))
        os.chmod(self.path, 0o600)
        listener.listen(16)
        self._listener = listener

    def serve_once(self) -> None:
        if self._listener is None:
            raise RuntimeError("MCP ingress server is not open")
        stream, _ = self._listener.accept()
        if _peer_uid(stream) != self._owner_uid:
            stream.close()
            return
        thread = Thread(target=self._handle_client, args=(stream,), daemon=True)
        with self._lock:
            self._clients.add(stream)
            self._threads.add(thread)
        thread.start()

    def close(self) -> None:
        listener, self._listener = self._listener, None
        if listener is not None:
            listener.close()
        with self._lock:
            clients = tuple(self._clients)
            threads = tuple(self._threads)
        for stream in clients:
            try:
                stream.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            stream.close()
        for thread in threads:
            thread.join(timeout=2)
        _remove_owned_socket(self.path, self._owner_uid)

    def _handle_client(self, stream: socket.socket) -> None:
        try:
            first = receive_mcp_ingress_frame(stream)
            if first.kind is McpIngressWireKind.BOOTSTRAP:
                self._bootstrap(stream, first)
            elif first.kind is McpIngressWireKind.SESSION:
                self._session(stream, first)
            else:
                self._error(stream, first, "mcp.ingress.handshake_required")
        except (EOFError, OSError, ValueError, PermissionError, RuntimeError):
            pass
        finally:
            stream.close()
            with self._lock:
                self._clients.discard(stream)
                self._threads.discard(current_thread())

    def _bootstrap(self, stream, message) -> None:
        client_id = _text_field(message.payload, "client_id")
        definition = self._identities.get(client_id)
        if definition is None:
            self._error(stream, message, "mcp.ingress.client_denied")
            return
        identity, ttl_seconds = definition
        token = self._tokens.issue(
            identity, datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
        self._respond(stream, message, McpIngressWireKind.TOKEN, {"token": token})

    def _session(self, stream, message) -> None:
        token = _text_field(message.payload, "token")
        ingress = AuthenticatedMcpIngress.authenticate(
            token, self._tokens, self._gateway,
        )
        self._respond(stream, message, McpIngressWireKind.READY, {"ready": True})
        while True:
            request = receive_mcp_ingress_frame(stream)
            if request.kind is McpIngressWireKind.LIST_TOOLS:
                tools = asyncio.run(ingress.list_tools())
                payload = {"tools": [_tool_document(item) for item in tools]}
                self._respond(stream, request, McpIngressWireKind.TOOLS, payload)
            elif request.kind is McpIngressWireKind.CALL_TOOL:
                name = _text_field(request.payload, "name")
                arguments = request.payload.get("arguments")
                if not isinstance(arguments, Mapping):
                    raise ValueError("MCP ingress arguments must be an object")
                outcome = asyncio.run(ingress.call_tool(name, _thaw(arguments)))
                self._respond(
                    stream, request, McpIngressWireKind.OUTCOME,
                    {"is_error": outcome.is_error, "safe_message": outcome.safe_message,
                     "structured_content": outcome.structured_content},
                )
            else:
                self._error(stream, request, "mcp.ingress.operation_denied")

    def _respond(self, stream, request, kind, payload) -> None:
        send_mcp_ingress_frame(stream, McpIngressWireMessage(
            f"mcp-response-{uuid4()}", kind, payload, request.message_id,
        ))

    def _error(self, stream, request, code) -> None:
        self._respond(stream, request, McpIngressWireKind.ERROR, {"code": code})


def _tool_document(tool):
    return {
        "name": tool.name, "capability_id": tool.capability_id,
        "title": tool.title, "description": tool.description,
        "input_schema": tool.input_schema, "output_schema": tool.output_schema,
    }


def _text_field(payload, name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"MCP ingress {name} must be text")
    return value


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _remove_owned_socket(path: Path, owner_uid: int) -> None:
    if not path.exists() and not path.is_symlink():
        return
    details = path.lstat()
    if not path.is_socket() or details.st_uid != owner_uid:
        raise PermissionError("refusing to replace unowned MCP ingress endpoint")
    path.unlink()


def _peer_uid(stream: socket.socket) -> int:
    if not hasattr(socket, "SO_PEERCRED"):
        raise RuntimeError("Unix peer credentials are unavailable")
    size = struct.calcsize("3i")
    raw = stream.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size)
    _process_id, user_id, _group_id = struct.unpack("3i", raw)
    return user_id
