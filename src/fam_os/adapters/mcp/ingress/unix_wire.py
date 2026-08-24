"""Strict bounded wire protocol for the owner-private MCP ingress socket."""

import json
import struct
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from fam_os.applications.identifiers import require_identifier
from fam_os.applications.payloads import freeze_payload


MCP_INGRESS_WIRE_VERSION = "fam.mcp-ingress.local/v1alpha1"
MAX_MCP_INGRESS_FRAME_BYTES = 1_048_576


class McpIngressWireKind(StrEnum):
    BOOTSTRAP = "bootstrap"
    SESSION = "session"
    LIST_TOOLS = "list_tools"
    CALL_TOOL = "call_tool"
    TOKEN = "token"
    READY = "ready"
    TOOLS = "tools"
    OUTCOME = "outcome"
    ERROR = "error"


_RESPONSES = {
    McpIngressWireKind.TOKEN, McpIngressWireKind.READY,
    McpIngressWireKind.TOOLS, McpIngressWireKind.OUTCOME,
    McpIngressWireKind.ERROR,
}


@dataclass(frozen=True, slots=True)
class McpIngressWireMessage:
    message_id: str
    kind: McpIngressWireKind
    payload: Mapping[str, object]
    correlation_id: str | None = None
    contract_version: str = MCP_INGRESS_WIRE_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "message_id", require_identifier(
            self.message_id, "MCP ingress message ID",
        ))
        if not isinstance(self.kind, McpIngressWireKind):
            raise ValueError("MCP ingress wire kind is invalid")
        if self.contract_version != MCP_INGRESS_WIRE_VERSION:
            raise ValueError("MCP ingress wire version is unsupported")
        object.__setattr__(self, "payload", freeze_payload(self.payload))
        if self.correlation_id is not None:
            object.__setattr__(self, "correlation_id", require_identifier(
                self.correlation_id, "MCP ingress correlation ID",
            ))
        if (self.kind in _RESPONSES) != (self.correlation_id is not None):
            raise ValueError("MCP ingress response correlation is invalid")


def send_mcp_ingress_frame(stream, message: McpIngressWireMessage) -> None:
    stream.sendall(encode_mcp_ingress_frame(message))


def encode_mcp_ingress_frame(message, maximum=MAX_MCP_INGRESS_FRAME_BYTES) -> bytes:
    document = {
        "contract_version": message.contract_version,
        "message_id": message.message_id,
        "kind": message.kind.value,
        "correlation_id": message.correlation_id,
        "payload": _thaw(message.payload),
    }
    payload = json.dumps(
        document, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    if not payload or len(payload) > maximum:
        raise ValueError("MCP ingress frame exceeds limit")
    return struct.pack("!I", len(payload)) + payload


def receive_mcp_ingress_frame(stream, maximum=MAX_MCP_INGRESS_FRAME_BYTES):
    size = struct.unpack("!I", _read_exact(stream, 4))[0]
    if size <= 0 or size > maximum:
        raise ValueError("MCP ingress frame size is invalid")
    try:
        document = json.loads(_read_exact(stream, size).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("MCP ingress frame is not strict UTF-8 JSON") from error
    fields = {"contract_version", "message_id", "kind", "correlation_id", "payload"}
    if not isinstance(document, dict) or set(document) != fields:
        raise ValueError("MCP ingress message fields must match exactly")
    if not isinstance(document["payload"], dict):
        raise ValueError("MCP ingress payload must be an object")
    try:
        kind = McpIngressWireKind(document["kind"])
    except (TypeError, ValueError) as error:
        raise ValueError("MCP ingress wire kind is invalid") from error
    return McpIngressWireMessage(
        document["message_id"], kind, document["payload"],
        document["correlation_id"], document["contract_version"],
    )


def _read_exact(stream, size: int) -> bytes:
    chunks = []
    while size:
        chunk = stream.recv(size)
        if not chunk:
            raise EOFError("MCP ingress transport closed during frame")
        chunks.append(chunk)
        size -= len(chunk)
    return b"".join(chunks)


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
