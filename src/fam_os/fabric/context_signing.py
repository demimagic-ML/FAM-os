"""Ed25519 creation and verification for exact-byte remote context."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.fabric.context import (
    REMOTE_CONTEXT_CONTRACT_VERSION,
    RemoteContextEnvelope,
    RemoteContextReceipt,
    RemoteContextReceiptStatus,
    RemoteRawContextFragment,
    RemoteTaskDescriptor,
    remote_context_content,
    remote_context_payload,
)
from fam_os.fabric.credentials import PersistentDeviceCredentials
from fam_os.fabric.identity import DeviceIdentity
from fam_os.fabric.privacy import RemoteContextSensitivity


def create_remote_context(
    credentials: PersistentDeviceCredentials, *, context_id: str, request_id: str,
    receiver_device_id: str, target_expert_id: str, purpose_id: str,
    workspace_id: str, sensitivity: RemoteContextSensitivity,
    descriptor: RemoteTaskDescriptor,
    raw_fragments: tuple[RemoteRawContextFragment, ...], issued_at: datetime,
) -> RemoteContextEnvelope:
    payload = remote_context_payload(
        target_expert_id=target_expert_id, purpose_id=purpose_id,
        workspace_id=workspace_id, sensitivity=sensitivity,
        descriptor=descriptor, raw_fragments=raw_fragments,
    )
    sender_device_id = credentials.identity.device_id
    expires_at = issued_at + timedelta(minutes=2)
    content_sha256 = hashlib.sha256(payload).hexdigest()
    signature = credentials.identity_key.sign(_context_signature_payload(
        context_id, request_id, sender_device_id, receiver_device_id,
        len(payload), content_sha256, issued_at, expires_at, payload,
    ))
    return RemoteContextEnvelope(
        context_id, request_id, sender_device_id, receiver_device_id,
        target_expert_id, purpose_id, workspace_id, sensitivity, descriptor,
        raw_fragments, len(payload), content_sha256, issued_at, expires_at,
        base64.b64encode(signature).decode("ascii"),
    )


def verify_remote_context(
    value: RemoteContextEnvelope, identity: DeviceIdentity, observed_at: datetime,
) -> None:
    if value.sender_device_id != identity.device_id:
        raise ValueError("remote context sender differs from enrolled identity")
    if not value.issued_at <= observed_at < value.expires_at:
        raise ValueError("remote context is outside its validity")
    _verify_signature(
        identity, value.signature_base64, _signed_context_payload(value),
        "remote context signature is invalid",
    )


def create_remote_context_receipt(
    credentials: PersistentDeviceCredentials, context: RemoteContextEnvelope,
    accepted_at: datetime,
) -> RemoteContextReceipt:
    receipt_id = "context-receipt-" + hashlib.sha256(
        f"{credentials.identity.device_id}|{context.context_id}|{context.content_sha256}".encode(),
    ).hexdigest()[:32]
    responder_device_id = credentials.identity.device_id
    status = RemoteContextReceiptStatus.ACCEPTED
    raw_fragment_count = len(context.raw_fragments)
    signature = credentials.identity_key.sign(_receipt_signature_payload(
        receipt_id, context.request_id, context.context_id,
        context.sender_device_id, responder_device_id, status,
        context.content_bytes, context.content_sha256,
        raw_fragment_count, accepted_at,
    ))
    return RemoteContextReceipt(
        receipt_id, context.request_id, context.context_id, context.sender_device_id,
        responder_device_id, status, context.content_bytes, context.content_sha256,
        raw_fragment_count, accepted_at, base64.b64encode(signature).decode("ascii"),
    )


def verify_remote_context_receipt(
    value: RemoteContextReceipt, context: RemoteContextEnvelope,
    identity: DeviceIdentity,
) -> None:
    expected = (
        context.request_id, context.context_id, context.sender_device_id,
        identity.device_id, context.content_bytes, context.content_sha256,
        len(context.raw_fragments),
    )
    actual = (
        value.request_id, value.context_id, value.sender_device_id,
        value.responder_device_id, value.content_bytes, value.content_sha256,
        value.raw_fragment_count,
    )
    if actual != expected:
        raise ValueError("remote context receipt differs from sent context")
    if (
        value.status is not RemoteContextReceiptStatus.ACCEPTED
        or not context.issued_at <= value.accepted_at < context.expires_at
    ):
        raise ValueError("remote context receipt acceptance is invalid")
    _verify_signature(
        identity, value.signature_base64, _receipt_payload(value),
        "remote context receipt signature is invalid",
    )


def _signed_context_payload(value: RemoteContextEnvelope) -> bytes:
    return _context_signature_payload(
        value.context_id, value.request_id, value.sender_device_id,
        value.receiver_device_id, value.content_bytes, value.content_sha256,
        value.issued_at, value.expires_at, remote_context_content(value),
    )


def _receipt_payload(value: RemoteContextReceipt) -> bytes:
    return _receipt_signature_payload(
        value.receipt_id, value.request_id, value.context_id,
        value.sender_device_id, value.responder_device_id, value.status,
        value.content_bytes, value.content_sha256, value.raw_fragment_count,
        value.accepted_at,
    )


def _context_signature_payload(
    context_id: str, request_id: str, sender_device_id: str,
    receiver_device_id: str, content_bytes: int, content_sha256: str,
    issued_at: datetime, expires_at: datetime, content: bytes,
) -> bytes:
    return _canonical({
        "contract_version": REMOTE_CONTEXT_CONTRACT_VERSION,
        "context_id": context_id, "request_id": request_id,
        "sender_device_id": sender_device_id,
        "receiver_device_id": receiver_device_id,
        "content_bytes": content_bytes, "content_sha256": content_sha256,
        "issued_at": issued_at.isoformat(), "expires_at": expires_at.isoformat(),
    }) + b"|" + content


def _receipt_signature_payload(
    receipt_id: str, request_id: str, context_id: str,
    sender_device_id: str, responder_device_id: str,
    status: RemoteContextReceiptStatus, content_bytes: int,
    content_sha256: str, raw_fragment_count: int, accepted_at: datetime,
) -> bytes:
    return _canonical({
        "contract_version": REMOTE_CONTEXT_CONTRACT_VERSION,
        "receipt_id": receipt_id, "request_id": request_id,
        "context_id": context_id, "sender_device_id": sender_device_id,
        "responder_device_id": responder_device_id, "status": status.value,
        "content_bytes": content_bytes, "content_sha256": content_sha256,
        "raw_fragment_count": raw_fragment_count,
        "accepted_at": accepted_at.isoformat(),
    })


def _verify_signature(identity, signature, payload, message) -> None:
    try:
        key = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(identity.public_key_base64, validate=True),
        )
        key.verify(base64.b64decode(signature, validate=True), payload)
    except (InvalidSignature, TypeError, ValueError) as error:
        raise ValueError(message) from error


def _canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
