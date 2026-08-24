"""Official-MCP-facing client for the running FAM ingress service."""

from __future__ import annotations

import asyncio
import os
import socket
from collections.abc import Mapping
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fam_os.adapters.mcp.ingress.types import McpIngressOutcome, McpIngressTool
from fam_os.adapters.mcp.ingress.unix_wire import (
    McpIngressWireKind,
    McpIngressWireMessage,
    receive_mcp_ingress_frame,
    send_mcp_ingress_frame,
)


class UnixMcpIngressClient:
    def __init__(self, stream: socket.socket) -> None:
        self._stream = stream
        self._lock = Lock()

    @classmethod
    def connect(cls, path: Path, client_id: str) -> "UnixMcpIngressClient":
        _require_private_socket(path)
        bootstrap = _connect(path)
        try:
            response = _exchange(
                bootstrap, McpIngressWireKind.BOOTSTRAP,
                {"client_id": client_id}, McpIngressWireKind.TOKEN,
            )
            token = _text(response.payload, "token")
        finally:
            bootstrap.close()
        stream = _connect(path)
        try:
            _exchange(
                stream, McpIngressWireKind.SESSION,
                {"token": token}, McpIngressWireKind.READY,
            )
        except BaseException:
            stream.close()
            raise
        return cls(stream)

    async def list_tools(self) -> tuple[McpIngressTool, ...]:
        return await asyncio.to_thread(self._list_tools)

    async def call_tool(self, tool_name: str, arguments: dict) -> McpIngressOutcome:
        return await asyncio.to_thread(self._call_tool, tool_name, arguments)

    def close(self) -> None:
        try:
            self._stream.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._stream.close()

    def _list_tools(self) -> tuple[McpIngressTool, ...]:
        with self._lock:
            response = _exchange(
                self._stream, McpIngressWireKind.LIST_TOOLS, {},
                McpIngressWireKind.TOOLS,
            )
        values = response.payload.get("tools")
        if not isinstance(values, tuple):
            raise ValueError("MCP ingress tools response is invalid")
        return tuple(_tool(value) for value in values)

    def _call_tool(self, tool_name: str, arguments: dict) -> McpIngressOutcome:
        with self._lock:
            response = _exchange(
                self._stream, McpIngressWireKind.CALL_TOOL,
                {"name": tool_name, "arguments": arguments},
                McpIngressWireKind.OUTCOME,
            )
        is_error = response.payload.get("is_error")
        content = response.payload.get("structured_content")
        if not isinstance(is_error, bool) or not isinstance(content, Mapping):
            raise ValueError("MCP ingress outcome response is invalid")
        return McpIngressOutcome(
            is_error, _text(response.payload, "safe_message"), _thaw(content),
        )


async def run_mcp_ingress_stdio(path: Path, client_id: str) -> None:
    from fam_os.adapters.mcp.ingress.sdk_server import OfficialMcpIngressServer

    client = UnixMcpIngressClient.connect(path, client_id)
    try:
        await OfficialMcpIngressServer(client).run_stdio()
    finally:
        client.close()


def _exchange(stream, kind, payload, expected):
    request = McpIngressWireMessage(f"mcp-request-{uuid4()}", kind, payload)
    send_mcp_ingress_frame(stream, request)
    response = receive_mcp_ingress_frame(stream)
    if response.correlation_id != request.message_id:
        raise ValueError("MCP ingress response correlation is invalid")
    if response.kind is McpIngressWireKind.ERROR:
        raise PermissionError(_text(response.payload, "code"))
    if response.kind is not expected:
        raise ValueError("MCP ingress response kind is invalid")
    return response


def _tool(value) -> McpIngressTool:
    if not isinstance(value, Mapping):
        raise ValueError("MCP ingress tool is invalid")
    return McpIngressTool(
        _text(value, "name"), _text(value, "capability_id"),
        _text(value, "title"), _text(value, "description"),
        _mapping(value, "input_schema"), _mapping(value, "output_schema"),
    )


def _text(value, name: str) -> str:
    item = value.get(name)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"MCP ingress {name} is invalid")
    return item


def _mapping(value, name: str) -> dict:
    item = value.get(name)
    if not isinstance(item, Mapping):
        raise ValueError(f"MCP ingress {name} is invalid")
    return _thaw(item)


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _connect(path: Path) -> socket.socket:
    stream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stream.connect(str(path))
    return stream


def _require_private_socket(path: Path) -> None:
    details = path.stat()
    if not path.is_socket() or details.st_uid != os.geteuid():
        raise PermissionError("MCP ingress socket is not owner controlled")
    if details.st_mode & 0o077:
        raise PermissionError("MCP ingress socket must be mode 0600")
