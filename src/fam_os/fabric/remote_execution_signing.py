"""Ed25519 binding for complete authenticated remote inference messages."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.fabric.context import RemoteContextEnvelope, RemoteContextReceipt
from fam_os.fabric.credentials import PersistentDeviceCredentials
from fam_os.fabric.identity import DeviceIdentity
from fam_os.fabric.peer_state import PeerCapabilityDeclaration
from fam_os.fabric.remote_execution import (
    REMOTE_EXECUTION_CONTRACT_VERSION,
    RemoteExecutionRequest,
    RemoteExecutionResult,
    RemoteExecutionStatus,
)
from fam_os.telemetry.contracts import InferenceMetrics


def create_remote_execution_request(
    credentials: PersistentDeviceCredentials,
    *,
    execution_id: str,
    plan_id: str,
    context: RemoteContextEnvelope,
    capability: PeerCapabilityDeclaration,
    context_tokens: int,
    maximum_output_tokens: int,
    json_output: bool,
    temperature: float,
) -> RemoteExecutionRequest:
    unsigned = RemoteExecutionRequest(
        execution_id, plan_id, context, capability, context_tokens,
        maximum_output_tokens, json_output, temperature, context.issued_at,
        _placeholder_signature(),
    )
    signature = credentials.identity_key.sign(_request_payload(unsigned))
    return RemoteExecutionRequest(
        unsigned.execution_id, unsigned.plan_id, unsigned.context,
        unsigned.capability, unsigned.context_tokens,
        unsigned.maximum_output_tokens, unsigned.json_output,
        unsigned.temperature, unsigned.issued_at,
        base64.b64encode(signature).decode("ascii"),
    )


def verify_remote_execution_request(
    value: RemoteExecutionRequest,
    identity: DeviceIdentity,
) -> None:
    if value.context.sender_device_id != identity.device_id:
        raise ValueError("remote execution sender differs from enrolled identity")
    _verify(
        identity, value.signature_base64, _request_payload(value),
        "remote execution request signature is invalid",
    )


def create_remote_execution_result(
    credentials: PersistentDeviceCredentials,
    request: RemoteExecutionRequest,
    receipt: RemoteContextReceipt,
    requester_certificate_sha256: str,
    *,
    status: RemoteExecutionStatus,
    content: str | None,
    failure_code: str | None,
    metrics: InferenceMetrics | None,
    started_at: datetime,
    completed_at: datetime,
) -> RemoteExecutionResult:
    encoded = b"" if content is None else content.encode("utf-8")
    unsigned = RemoteExecutionResult(
        request.execution_id, request.plan_id, request.context.request_id,
        credentials.identity.device_id, requester_certificate_sha256,
        status, request.capability.model_ref,
        content, len(encoded), hashlib.sha256(encoded).hexdigest(), failure_code,
        metrics, receipt, started_at, completed_at, _placeholder_signature(),
    )
    signature = credentials.identity_key.sign(_result_payload(unsigned))
    return RemoteExecutionResult(
        unsigned.execution_id, unsigned.plan_id, unsigned.request_id,
        unsigned.responder_device_id, unsigned.requester_certificate_sha256,
        unsigned.status, unsigned.model_ref,
        unsigned.content, unsigned.content_bytes, unsigned.content_sha256,
        unsigned.failure_code, unsigned.metrics, unsigned.context_receipt,
        unsigned.started_at, unsigned.completed_at,
        base64.b64encode(signature).decode("ascii"),
    )


def verify_remote_execution_result(
    value: RemoteExecutionResult,
    request: RemoteExecutionRequest,
    identity: DeviceIdentity,
    requester_certificate_sha256: str,
) -> None:
    expected = (
        request.execution_id, request.plan_id, request.context.request_id,
        identity.device_id, request.capability.model_ref,
        request.context.context_id, requester_certificate_sha256,
    )
    actual = (
        value.execution_id, value.plan_id, value.request_id,
        value.responder_device_id, value.model_ref,
        value.context_receipt.context_id, value.requester_certificate_sha256,
    )
    if actual != expected:
        raise ValueError("remote execution result differs from request")
    if value.content_bytes > request.context.descriptor.maximum_output_bytes:
        raise ValueError("remote execution result exceeds authorized output")
    _verify(
        identity, value.signature_base64, _result_payload(value),
        "remote execution result signature is invalid",
    )


def _request_payload(value: RemoteExecutionRequest) -> bytes:
    return _canonical({
        "contract_version": REMOTE_EXECUTION_CONTRACT_VERSION,
        "execution_id": value.execution_id,
        "plan_id": value.plan_id,
        "context_id": value.context.context_id,
        "context_sha256": value.context.content_sha256,
        "context_signature_base64": value.context.signature_base64,
        "capability_declaration_id": value.capability.declaration_id,
        "capability_signature_base64": value.capability.signature_base64,
        "context_tokens": value.context_tokens,
        "maximum_output_tokens": value.maximum_output_tokens,
        "json_output": value.json_output,
        "temperature": value.temperature,
        "issued_at": value.issued_at.isoformat(),
    })


def _result_payload(value: RemoteExecutionResult) -> bytes:
    return _canonical({
        "contract_version": REMOTE_EXECUTION_CONTRACT_VERSION,
        "execution_id": value.execution_id,
        "plan_id": value.plan_id,
        "request_id": value.request_id,
        "responder_device_id": value.responder_device_id,
        "requester_certificate_sha256": value.requester_certificate_sha256,
        "status": value.status.value,
        "model_ref": value.model_ref,
        "content_bytes": value.content_bytes,
        "content_sha256": value.content_sha256,
        "failure_code": value.failure_code,
        "metrics": _metrics(value.metrics),
        "context_receipt_id": value.context_receipt.receipt_id,
        "context_receipt_signature_base64": value.context_receipt.signature_base64,
        "started_at": value.started_at.isoformat(),
        "completed_at": value.completed_at.isoformat(),
    })


def _metrics(value: InferenceMetrics | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "model_ref": value.model_ref,
        "wall_seconds": value.wall_seconds,
        "load_seconds": value.load_seconds,
        "prompt_tokens": value.prompt_tokens,
        "output_tokens": value.output_tokens,
        "generation_tokens_per_second": value.generation_tokens_per_second,
    }


def _verify(identity: DeviceIdentity, signature: str, payload: bytes, message: str) -> None:
    try:
        key = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(identity.public_key_base64, validate=True),
        )
        key.verify(base64.b64decode(signature, validate=True), payload)
    except (InvalidSignature, TypeError, ValueError) as error:
        raise ValueError(message) from error


def _placeholder_signature() -> str:
    return base64.b64encode(bytes(64)).decode("ascii")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
