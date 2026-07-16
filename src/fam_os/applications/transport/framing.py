"""Bounded canonical JSON framing for local Unix streams."""

import json
import struct

from fam_os.applications.transport.wire import (
    LocalMessage, message_document, message_from_document,
)


MAX_FRAME_BYTES = 1_048_576
HEADER_BYTES = 4


def encode_frame(message: LocalMessage, maximum_bytes: int = MAX_FRAME_BYTES) -> bytes:
    payload = json.dumps(
        message_document(message), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    if not payload or len(payload) > maximum_bytes:
        raise ValueError("local message exceeds frame limit")
    return struct.pack("!I", len(payload)) + payload


def receive_frame(stream, maximum_bytes: int = MAX_FRAME_BYTES) -> LocalMessage:
    header = _read_exact(stream, HEADER_BYTES)
    size = struct.unpack("!I", header)[0]
    if size <= 0 or size > maximum_bytes:
        raise ValueError("local frame size is invalid")
    payload = _read_exact(stream, size)
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("local frame is not valid UTF-8 JSON") from error
    return message_from_document(document)


def send_frame(stream, message: LocalMessage, maximum_bytes: int = MAX_FRAME_BYTES) -> None:
    stream.sendall(encode_frame(message, maximum_bytes))


def _read_exact(stream, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.recv(remaining)
        if not chunk:
            raise EOFError("local transport closed during frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
