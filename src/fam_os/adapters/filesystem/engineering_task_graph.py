"""Private append-only JSONL adapter for restart-safe engineering task graphs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from threading import Lock

from fam_os.core.engineering.repository import EngineeringTaskGraphEvent
from fam_os.schemas import decode_document, encode_document


_MAX_RECORD_BYTES = 1_048_576
_RECORD_KEYS = {"event", "previous_record_sha256", "record_sha256"}


class JsonlEngineeringTaskGraphRepository:
    def __init__(self, path: Path) -> None:
        if not path.is_absolute():
            raise ValueError("engineering task graph path must be absolute")
        if not path.parent.is_dir() or path.parent.is_symlink():
            raise ValueError("engineering task graph parent must be an existing directory")
        self._path = path
        self._lock = Lock()

    def append(self, expected_sequence: int, event: EngineeringTaskGraphEvent) -> bool:
        with self._lock:
            records = self._records()
            history = tuple(item[0] for item in records if item[0].graph_id == event.graph_id)
            current = -1 if not history else history[-1].sequence
            if current != expected_sequence or event.sequence != current + 1:
                return False
            previous = "0" * 64 if not records else records[-1][1]
            document = encode_document(event)
            record_sha256 = _record_digest(previous, document)
            payload = json.dumps({
                "event": document,
                "previous_record_sha256": previous,
                "record_sha256": record_sha256,
            }, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            if len(payload) > _MAX_RECORD_BYTES:
                raise ValueError("engineering task graph record exceeds its bound")
            descriptor = os.open(
                self._path,
                os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW,
                0o600,
            )
            try:
                if os.fstat(descriptor).st_mode & 0o077:
                    raise PermissionError("engineering task graph log is not owner-private")
                written = os.write(descriptor, payload)
                if written != len(payload):
                    raise OSError("engineering task graph append was partial")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            return True

    def history(self, graph_id: str) -> tuple[EngineeringTaskGraphEvent, ...]:
        if not graph_id.strip():
            raise ValueError("graph_id must be nonempty")
        with self._lock:
            return tuple(
                event for event, _digest in self._records()
                if event.graph_id == graph_id
            )

    def _records(self) -> tuple[tuple[EngineeringTaskGraphEvent, str], ...]:
        if not self._path.exists():
            return ()
        if self._path.is_symlink() or not self._path.is_file():
            raise PermissionError("engineering task graph log is unsafe")
        content = self._path.read_bytes()
        if content and not content.endswith(b"\n"):
            raise ValueError("engineering task graph log has a partial final record")
        previous = "0" * 64
        records = []
        for line in content.splitlines():
            if not line or len(line) > _MAX_RECORD_BYTES:
                raise ValueError("engineering task graph log record is invalid")
            document = json.loads(line, object_pairs_hook=_strict_object)
            if not isinstance(document, dict) or set(document) != _RECORD_KEYS:
                raise ValueError("engineering task graph log shape is invalid")
            if document["previous_record_sha256"] != previous:
                raise ValueError("engineering task graph hash chain is discontinuous")
            expected = _record_digest(previous, document["event"])
            if document["record_sha256"] != expected:
                raise ValueError("engineering task graph record digest is invalid")
            event = decode_document(document["event"])
            if not isinstance(event, EngineeringTaskGraphEvent):
                raise ValueError("engineering task graph log contains the wrong contract")
            records.append((event, expected))
            previous = expected
        return tuple(records)


def _record_digest(previous: str, event_document: object) -> str:
    event = json.dumps(
        event_document, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(previous.encode("ascii") + b"\n" + event).hexdigest()


def _strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("engineering task graph log contains duplicate keys")
        value[key] = item
    return value
