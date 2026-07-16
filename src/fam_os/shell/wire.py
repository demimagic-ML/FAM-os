"""Strict bounded JSON wire protocol between FAM Shell and local Core."""

import json
import struct
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from fam_os.applications.identifiers import require_identifier
from fam_os.applications.payloads import freeze_payload
from fam_os.schemas import decode_document, encode_document
from fam_os.shell.contracts import (
    ShellAskCommand,
    ShellCancelCommand,
    ShellDecisionCommand,
    ShellSessionSnapshot,
    ShellSnapshotQuery,
)


SHELL_TRANSPORT_VERSION = "fam.shell.local/v1alpha1"
MAX_SHELL_FRAME_BYTES = 1_048_576


class ShellWireKind(StrEnum):
    ASK = "ask"
    SNAPSHOT_QUERY = "snapshot_query"
    DECIDE = "decide"
    CANCEL = "cancel"
    SNAPSHOT = "snapshot"
    ERROR = "error"


REQUEST_TYPES = {
    ShellWireKind.ASK: ShellAskCommand,
    ShellWireKind.SNAPSHOT_QUERY: ShellSnapshotQuery,
    ShellWireKind.DECIDE: ShellDecisionCommand,
    ShellWireKind.CANCEL: ShellCancelCommand,
}
RESPONSE_KINDS = {ShellWireKind.SNAPSHOT, ShellWireKind.ERROR}


@dataclass(frozen=True, slots=True)
class ShellWireMessage:
    message_id: str
    kind: ShellWireKind
    payload: Mapping[str, object]
    correlation_id: str | None = None
    contract_version: str = SHELL_TRANSPORT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "message_id", require_identifier(self.message_id, "message_id"))
        if not isinstance(self.kind, ShellWireKind):
            raise ValueError("shell wire kind is invalid")
        if self.contract_version != SHELL_TRANSPORT_VERSION:
            raise ValueError("unsupported shell transport version")
        object.__setattr__(self, "payload", freeze_payload(self.payload))
        if self.correlation_id is not None:
            object.__setattr__(
                self, "correlation_id",
                require_identifier(self.correlation_id, "correlation_id"),
            )
        if (self.kind in RESPONSE_KINDS) != (self.correlation_id is not None):
            raise ValueError("shell response correlation is invalid")


def request_message(message_id: str, kind: ShellWireKind, value) -> ShellWireMessage:
    expected = REQUEST_TYPES.get(kind)
    if expected is None or not isinstance(value, expected):
        raise ValueError("shell request payload type is invalid")
    return ShellWireMessage(message_id, kind, encode_document(value))


def snapshot_message(
    message_id: str, correlation_id: str, value: ShellSessionSnapshot,
) -> ShellWireMessage:
    return ShellWireMessage(
        message_id, ShellWireKind.SNAPSHOT, encode_document(value), correlation_id
    )


def error_message(message_id: str, correlation_id: str, code: str) -> ShellWireMessage:
    return ShellWireMessage(
        message_id, ShellWireKind.ERROR,
        {"code": require_identifier(code, "error code")}, correlation_id,
    )


def decode_request(message: ShellWireMessage):
    expected = REQUEST_TYPES.get(message.kind)
    if expected is None:
        raise ValueError("message is not a shell request")
    value = decode_document(_thaw(message.payload))
    if not isinstance(value, expected):
        raise ValueError("shell request schema does not match message kind")
    return value


def decode_snapshot(message: ShellWireMessage) -> ShellSessionSnapshot:
    if message.kind is not ShellWireKind.SNAPSHOT:
        raise ValueError("message is not a shell snapshot")
    value = decode_document(_thaw(message.payload))
    if not isinstance(value, ShellSessionSnapshot):
        raise ValueError("shell response schema is invalid")
    return value


def encode_frame(message: ShellWireMessage, maximum=MAX_SHELL_FRAME_BYTES) -> bytes:
    payload = json.dumps(
        message_document(message), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    if not payload or len(payload) > maximum:
        raise ValueError("shell frame exceeds limit")
    return struct.pack("!I", len(payload)) + payload


def send_frame(stream, message, maximum=MAX_SHELL_FRAME_BYTES) -> None:
    stream.sendall(encode_frame(message, maximum))


def receive_frame(stream, maximum=MAX_SHELL_FRAME_BYTES) -> ShellWireMessage:
    header = _read_exact(stream, 4)
    size = struct.unpack("!I", header)[0]
    if size <= 0 or size > maximum:
        raise ValueError("shell frame size is invalid")
    try:
        document = json.loads(_read_exact(stream, size).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("shell frame is not strict UTF-8 JSON") from error
    return message_from_document(document)


def message_document(message: ShellWireMessage) -> dict[str, object]:
    return {
        "contract_version": message.contract_version,
        "message_id": message.message_id,
        "kind": message.kind.value,
        "correlation_id": message.correlation_id,
        "payload": _thaw(message.payload),
    }


def message_from_document(document) -> ShellWireMessage:
    fields = {"contract_version", "message_id", "kind", "correlation_id", "payload"}
    if not isinstance(document, dict) or set(document) != fields:
        raise ValueError("shell message fields must match exactly")
    if not isinstance(document["payload"], dict):
        raise ValueError("shell message payload must be an object")
    try:
        kind = ShellWireKind(document["kind"])
    except (TypeError, ValueError) as error:
        raise ValueError("shell wire kind is invalid") from error
    return ShellWireMessage(
        document["message_id"], kind, document["payload"],
        document["correlation_id"], document["contract_version"],
    )


def _read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.recv(remaining)
        if not chunk:
            raise EOFError("shell transport closed during frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
