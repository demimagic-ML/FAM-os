"""Strict Console parsing for owner-approved peer context transfer."""

from urllib.parse import unquote

from fam_os.console.tasks import task_document
from fam_os.fabric import (
    RemoteContextSensitivity,
    RemoteContextSendRequest,
    RemoteRawContextFragment,
    RemoteRawContextKind,
    RemoteTaskDescriptor,
)

_FIELDS = {
    "request_id", "target_expert_id", "capability_declaration_id",
    "expected_privacy_revision", "purpose_id", "workspace_id", "sensitivity",
    "intent_id", "capability_ids", "assurance_id", "maximum_output_bytes",
    "raw_fragments", "confirmed",
}
_FRAGMENT_FIELDS = {
    "fragment_id", "kind", "source_sha256", "content", "content_sha256",
}


def handle_peer_context_post(handler, path: str, document: dict) -> bool:
    parts = path.strip("/").split("/")
    if len(parts) != 5 or parts[:3] != ["api", "v1", "peers"] or parts[4] != "context":
        return False
    if set(document) != _FIELDS:
        raise ValueError("peer context fields are not exact")
    enrollment_id = unquote(parts[3])
    request = RemoteContextSendRequest(
        _text(document, "request_id"), enrollment_id,
        _text(document, "target_expert_id"),
        _text(document, "capability_declaration_id"),
        _positive(document, "expected_privacy_revision"),
        _text(document, "purpose_id"), _text(document, "workspace_id"),
        RemoteContextSensitivity(_text(document, "sensitivity")),
        RemoteTaskDescriptor(
            _text(document, "intent_id"), _texts(document, "capability_ids"),
            _text(document, "assurance_id"),
            _positive(document, "maximum_output_bytes"),
        ),
        _fragments(document.get("raw_fragments")),
        _boolean(document, "confirmed"),
    )
    handler._json(200, task_document(handler.server.peer_api.send_context(request)))
    return True


def _fragments(value) -> tuple[RemoteRawContextFragment, ...]:
    if not isinstance(value, list):
        raise TypeError("raw_fragments must be an array")
    fragments = []
    for item in value:
        if not isinstance(item, dict) or set(item) != _FRAGMENT_FIELDS:
            raise ValueError("remote context fragment fields are not exact")
        fragments.append(RemoteRawContextFragment(
            _mapping_text(item, "fragment_id"),
            RemoteRawContextKind(_mapping_text(item, "kind")),
            _mapping_text(item, "source_sha256"),
            _mapping_text(item, "content"),
            _mapping_text(item, "content_sha256"),
        ))
    return tuple(fragments)


def _text(document, field: str) -> str:
    return _mapping_text(document, field)


def _mapping_text(document, field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field} must be non-empty text")
    return value


def _texts(document, field: str) -> tuple[str, ...]:
    value = document.get(field)
    if not isinstance(value, list) or not value:
        raise TypeError(f"{field} must be a non-empty array")
    return tuple(_array_text(item, field) for item in value)


def _array_text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field} entries must be non-empty text")
    return value


def _positive(document, field: str) -> int:
    value = document.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise TypeError(f"{field} must be a positive integer")
    return value


def _boolean(document, field: str) -> bool:
    value = document.get(field)
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be boolean")
    return value
