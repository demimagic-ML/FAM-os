"""Signed, exact-byte remote context with no execution or action authority."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from fam_os.experts.capabilities import require_expert_capabilities
from fam_os.fabric.privacy import RemoteContextSensitivity

REMOTE_CONTEXT_CONTRACT_VERSION = "fam.fabric.minimum-context/v1alpha1"
MAX_REMOTE_CONTEXT_BYTES = 262_144
_ID = re.compile(r"^[a-z][a-z0-9_.:-]{0,127}$")


class RemoteRawContextKind(StrEnum):
    PROMPT = "prompt"
    FILE_EXCERPT = "file_excerpt"
    MEMORY = "memory"
    RETRIEVAL = "retrieval"


@dataclass(frozen=True, slots=True)
class RemoteTaskDescriptor:
    intent_id: str
    capability_ids: tuple[str, ...]
    assurance_id: str
    maximum_output_bytes: int

    def __post_init__(self) -> None:
        _identifier(self.intent_id, "remote intent")
        require_expert_capabilities(self.capability_ids)
        if self.assurance_id not in {"unverified", "grounded", "verified"}:
            raise ValueError("remote assurance is invalid")
        if not 1 <= self.maximum_output_bytes <= MAX_REMOTE_CONTEXT_BYTES:
            raise ValueError("remote output bound is invalid")


@dataclass(frozen=True, slots=True)
class RemoteRawContextFragment:
    fragment_id: str
    kind: RemoteRawContextKind
    source_sha256: str
    content: str
    content_sha256: str

    def __post_init__(self) -> None:
        _identifier(self.fragment_id, "remote fragment")
        if not isinstance(self.kind, RemoteRawContextKind):
            raise TypeError("remote raw fragment kind is invalid")
        _digest(self.source_sha256, "remote source")
        encoded = self.content.encode("utf-8")
        if not encoded or len(encoded) > MAX_REMOTE_CONTEXT_BYTES:
            raise ValueError("remote raw fragment byte size is invalid")
        if hashlib.sha256(encoded).hexdigest() != self.content_sha256:
            raise ValueError("remote raw fragment digest is invalid")


@dataclass(frozen=True, slots=True)
class RemoteContextEnvelope:
    context_id: str
    request_id: str
    sender_device_id: str
    receiver_device_id: str
    target_expert_id: str
    purpose_id: str
    workspace_id: str
    sensitivity: RemoteContextSensitivity
    descriptor: RemoteTaskDescriptor
    raw_fragments: tuple[RemoteRawContextFragment, ...]
    content_bytes: int
    content_sha256: str
    issued_at: datetime
    expires_at: datetime
    signature_base64: str
    contract_version: str = REMOTE_CONTEXT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value, name in (
            (self.context_id, "remote context"), (self.request_id, "remote request"),
            (self.sender_device_id, "sender device"),
            (self.receiver_device_id, "receiver device"),
            (self.target_expert_id, "target expert"),
            (self.purpose_id, "remote purpose"), (self.workspace_id, "remote workspace"),
        ):
            _identifier(value, name)
        if len({item.fragment_id for item in self.raw_fragments}) != len(self.raw_fragments):
            raise ValueError("remote context fragment identities must be unique")
        if not isinstance(self.sensitivity, RemoteContextSensitivity):
            raise TypeError("remote context sensitivity is invalid")
        if not 1 <= self.content_bytes <= MAX_REMOTE_CONTEXT_BYTES:
            raise ValueError("remote context byte bound is invalid")
        _digest(self.content_sha256, "remote context")
        _time(self.issued_at)
        _time(self.expires_at)
        if not self.issued_at < self.expires_at <= self.issued_at + timedelta(minutes=2):
            raise ValueError("remote context validity is invalid")
        if self.contract_version != REMOTE_CONTEXT_CONTRACT_VERSION:
            raise ValueError("remote context contract is unsupported")
        _signature(self.signature_base64, "remote context")
        _verify_content(self)

    @property
    def contains_raw_content(self) -> bool:
        return bool(self.raw_fragments)


class RemoteContextReceiptStatus(StrEnum):
    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class RemoteContextReceipt:
    receipt_id: str
    request_id: str
    context_id: str
    sender_device_id: str
    responder_device_id: str
    status: RemoteContextReceiptStatus
    content_bytes: int
    content_sha256: str
    raw_fragment_count: int
    accepted_at: datetime
    signature_base64: str
    contract_version: str = REMOTE_CONTEXT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value, name in (
            (self.receipt_id, "context receipt"), (self.request_id, "context request"),
            (self.context_id, "context"), (self.sender_device_id, "sender device"),
            (self.responder_device_id, "responder device"),
        ):
            _identifier(value, name)
        if not 1 <= self.content_bytes <= MAX_REMOTE_CONTEXT_BYTES:
            raise ValueError("context receipt byte count is invalid")
        if not isinstance(self.status, RemoteContextReceiptStatus):
            raise TypeError("remote context receipt status is invalid")
        _digest(self.content_sha256, "context receipt")
        if self.raw_fragment_count < 0:
            raise ValueError("context receipt fragment count is invalid")
        _time(self.accepted_at)
        if self.contract_version != REMOTE_CONTEXT_CONTRACT_VERSION:
            raise ValueError("remote context contract is unsupported")
        _signature(self.signature_base64, "remote context receipt")


def remote_context_content(value: RemoteContextEnvelope) -> bytes:
    return remote_context_payload(
        target_expert_id=value.target_expert_id,
        purpose_id=value.purpose_id,
        workspace_id=value.workspace_id,
        sensitivity=value.sensitivity,
        descriptor=value.descriptor,
        raw_fragments=value.raw_fragments,
    )


def remote_context_payload(
    *, target_expert_id: str, purpose_id: str, workspace_id: str,
    sensitivity: RemoteContextSensitivity, descriptor: RemoteTaskDescriptor,
    raw_fragments: tuple[RemoteRawContextFragment, ...],
) -> bytes:
    """Return the exact disclosed payload without constructing an invalid envelope."""
    _identifier(target_expert_id, "target expert")
    _identifier(purpose_id, "remote purpose")
    _identifier(workspace_id, "remote workspace")
    if not isinstance(sensitivity, RemoteContextSensitivity):
        raise TypeError("remote context sensitivity is invalid")
    if not isinstance(descriptor, RemoteTaskDescriptor):
        raise TypeError("remote context descriptor is invalid")
    if len({item.fragment_id for item in raw_fragments}) != len(raw_fragments):
        raise ValueError("remote context fragment identities must be unique")
    document = {
        "target_expert_id": target_expert_id,
        "purpose_id": purpose_id, "workspace_id": workspace_id,
        "sensitivity": sensitivity.value,
        "descriptor": {
            "intent_id": descriptor.intent_id,
            "capability_ids": descriptor.capability_ids,
            "assurance_id": descriptor.assurance_id,
            "maximum_output_bytes": descriptor.maximum_output_bytes,
        },
        "raw_fragments": tuple({
            "fragment_id": item.fragment_id, "kind": item.kind.value,
            "source_sha256": item.source_sha256, "content": item.content,
            "content_sha256": item.content_sha256,
        } for item in raw_fragments),
    }
    return _canonical(document)


def _verify_content(value) -> None:
    payload = remote_context_content(value)
    if len(payload) != value.content_bytes or hashlib.sha256(payload).hexdigest() != value.content_sha256:
        raise ValueError("remote context exact-byte evidence is invalid")


def _canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _identifier(value: str, name: str) -> None:
    if not _ID.fullmatch(value):
        raise ValueError(f"{name} is not a canonical identifier")


def _digest(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} digest is invalid")


def _signature(value: str, name: str) -> None:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, TypeError, ValueError) as error:
        raise ValueError(f"{name} signature is invalid") from error
    if len(decoded) != 64:
        raise ValueError(f"{name} signature is invalid")


def _time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("remote context timestamps must be timezone-aware")
