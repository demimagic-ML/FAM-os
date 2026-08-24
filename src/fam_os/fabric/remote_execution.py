"""Owner authority and content-free route plan for Core-owned remote inference."""

from __future__ import annotations

import base64
import binascii
import hashlib
import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.fabric.context import (
    MAX_REMOTE_CONTEXT_BYTES,
    RemoteContextEnvelope,
    RemoteContextReceipt,
    RemoteTaskDescriptor,
)
from fam_os.fabric.peer_state import PeerCapabilityDeclaration
from fam_os.fabric.privacy import RemoteContextSensitivity
from fam_os.telemetry.contracts import InferenceMetrics

REMOTE_EXECUTION_CONTRACT_VERSION = "fam.fabric.remote-execution/v1alpha1"
_ID = re.compile(r"^[a-z][a-z0-9_.:-]{0,127}$")
MAX_REMOTE_CONTEXT_TOKENS = 65_536
MAX_REMOTE_OUTPUT_TOKENS = 8_192


@dataclass(frozen=True, slots=True)
class RemoteExecutionAuthority:
    enrollment_id: str
    expected_privacy_revision: int
    purpose_id: str
    workspace_id: str
    sensitivity: RemoteContextSensitivity
    maximum_context_bytes: int
    maximum_output_bytes: int
    confirmed: bool
    contract_version: str = REMOTE_EXECUTION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value, name in (
            (self.enrollment_id, "remote enrollment"),
            (self.purpose_id, "remote purpose"),
            (self.workspace_id, "remote workspace"),
        ):
            _identifier(value, name)
        if not isinstance(self.sensitivity, RemoteContextSensitivity):
            raise TypeError("remote execution sensitivity is invalid")
        if self.expected_privacy_revision < 1:
            raise ValueError("remote execution privacy revision is invalid")
        for bound, name in (
            (self.maximum_context_bytes, "context"),
            (self.maximum_output_bytes, "output"),
        ):
            if isinstance(bound, bool) or not 1 <= bound <= MAX_REMOTE_CONTEXT_BYTES:
                raise ValueError(f"remote execution {name} bound is invalid")
        if not self.confirmed:
            raise PermissionError("remote execution requires explicit confirmation")
        if self.contract_version != REMOTE_EXECUTION_CONTRACT_VERSION:
            raise ValueError("remote execution contract is unsupported")


@dataclass(frozen=True, slots=True)
class RemoteExecutionPlan:
    plan_id: str
    instance_id: str
    request_id: str
    enrollment_id: str
    peer_device_id: str
    expert_id: str
    model_ref: str
    expert_tier: str
    capability_declaration_id: str
    expected_privacy_revision: int
    purpose_id: str
    workspace_id: str
    sensitivity: RemoteContextSensitivity
    descriptor: RemoteTaskDescriptor
    maximum_context_bytes: int
    predicted_completion_milliseconds: float
    reason_codes: tuple[str, ...]
    created_at: datetime
    contract_version: str = REMOTE_EXECUTION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value, name in (
            (self.plan_id, "remote execution plan"),
            (self.enrollment_id, "remote enrollment"),
            (self.peer_device_id, "remote peer"), (self.expert_id, "remote expert"),
            (self.capability_declaration_id, "remote capability declaration"),
            (self.purpose_id, "remote purpose"),
            (self.workspace_id, "remote workspace"),
        ):
            _identifier(value, name)
        _text(self.instance_id, "Core instance")
        _text(self.request_id, "Core request")
        if not self.model_ref.strip() or len(self.model_ref) > 256:
            raise ValueError("remote execution model reference is invalid")
        if self.expert_tier not in {
            "economical", "specialist", "escalation", "embedding",
        }:
            raise ValueError("remote execution expert tier is invalid")
        if not isinstance(self.sensitivity, RemoteContextSensitivity):
            raise TypeError("remote execution plan sensitivity is invalid")
        if self.expected_privacy_revision < 1:
            raise ValueError("remote execution plan privacy revision is invalid")
        if not 1 <= self.maximum_context_bytes <= MAX_REMOTE_CONTEXT_BYTES:
            raise ValueError("remote execution context bound is invalid")
        if self.predicted_completion_milliseconds < 0:
            raise ValueError("remote execution prediction is invalid")
        if not self.reason_codes or len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("remote execution reasons are invalid")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("remote execution plan timestamp must be timezone-aware")
        if self.contract_version != REMOTE_EXECUTION_CONTRACT_VERSION:
            raise ValueError("remote execution contract is unsupported")


@dataclass(frozen=True, slots=True)
class RemoteExecutionRequest:
    execution_id: str
    plan_id: str
    context: RemoteContextEnvelope
    capability: PeerCapabilityDeclaration
    context_tokens: int
    maximum_output_tokens: int
    json_output: bool
    temperature: float
    issued_at: datetime
    signature_base64: str
    contract_version: str = REMOTE_EXECUTION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _identifier(self.execution_id, "remote execution")
        _identifier(self.plan_id, "remote execution plan")
        if self.context.receiver_device_id != self.capability.device_id:
            raise ValueError("remote execution capability belongs to another device")
        if self.context.target_expert_id != self.capability.expert_id:
            raise ValueError("remote execution capability targets another expert")
        if not set(self.context.descriptor.capability_ids).issubset(
            self.capability.capability_ids,
        ):
            raise ValueError("remote execution capability does not cover the task")
        if self.context.content_bytes > self.capability.maximum_context_bytes:
            raise ValueError("remote execution context exceeds capability")
        if (
            isinstance(self.context_tokens, bool)
            or not 1 <= self.context_tokens <= MAX_REMOTE_CONTEXT_TOKENS
            or self.context_tokens * 4 > self.capability.maximum_context_bytes
        ):
            raise ValueError("remote execution context-token bound is invalid")
        if (
            isinstance(self.maximum_output_tokens, bool)
            or not 1 <= self.maximum_output_tokens <= MAX_REMOTE_OUTPUT_TOKENS
        ):
            raise ValueError("remote execution output-token bound is invalid")
        if not isinstance(self.json_output, bool):
            raise TypeError("remote execution JSON setting is invalid")
        if (
            isinstance(self.temperature, bool)
            or not isinstance(self.temperature, (int, float))
            or not math.isfinite(self.temperature)
            or not 0 <= self.temperature <= 2
        ):
            raise ValueError("remote execution temperature is invalid")
        _time(self.issued_at)
        if self.issued_at != self.context.issued_at:
            raise ValueError("remote execution timestamp differs from context")
        _signature(self.signature_base64, "remote execution request")
        if self.contract_version != REMOTE_EXECUTION_CONTRACT_VERSION:
            raise ValueError("remote execution contract is unsupported")


class RemoteExecutionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RemoteExecutionResult:
    execution_id: str
    plan_id: str
    request_id: str
    responder_device_id: str
    requester_certificate_sha256: str
    status: RemoteExecutionStatus
    model_ref: str
    content: str | None
    content_bytes: int
    content_sha256: str
    failure_code: str | None
    metrics: InferenceMetrics | None
    context_receipt: RemoteContextReceipt
    started_at: datetime
    completed_at: datetime
    signature_base64: str
    contract_version: str = REMOTE_EXECUTION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value, name in (
            (self.execution_id, "remote execution"),
            (self.plan_id, "remote execution plan"),
            (self.request_id, "remote request"),
            (self.responder_device_id, "remote responder"),
        ):
            _identifier(value, name)
        _digest(self.requester_certificate_sha256, "remote requester certificate")
        if not self.model_ref.strip() or len(self.model_ref) > 256:
            raise ValueError("remote execution result model is invalid")
        if not isinstance(self.status, RemoteExecutionStatus):
            raise TypeError("remote execution result status is invalid")
        content = b"" if self.content is None else self.content.encode("utf-8")
        if len(content) != self.content_bytes:
            raise ValueError("remote execution result byte count is invalid")
        _digest(self.content_sha256, "remote execution result")
        if hashlib.sha256(content).hexdigest() != self.content_sha256:
            raise ValueError("remote execution result content digest is invalid")
        completed = self.status is RemoteExecutionStatus.COMPLETED
        if completed != bool(self.content):
            raise ValueError("remote execution content does not match status")
        if completed != (self.metrics is not None):
            raise ValueError("remote execution metrics do not match status")
        if completed != (self.failure_code is None):
            raise ValueError("remote execution failure does not match status")
        if self.metrics is not None and self.metrics.model_ref != self.model_ref:
            raise ValueError("remote execution metrics belong to another model")
        if self.failure_code is not None:
            _identifier(self.failure_code, "remote execution failure")
        if self.context_receipt.request_id != self.request_id:
            raise ValueError("remote execution receipt belongs to another request")
        if self.context_receipt.responder_device_id != self.responder_device_id:
            raise ValueError("remote execution receipt belongs to another responder")
        _time(self.started_at)
        _time(self.completed_at)
        if self.completed_at < self.started_at:
            raise ValueError("remote execution result time ordering is invalid")
        _signature(self.signature_base64, "remote execution result")
        if self.contract_version != REMOTE_EXECUTION_CONTRACT_VERSION:
            raise ValueError("remote execution contract is unsupported")


def _identifier(value: str, name: str) -> None:
    if not _ID.fullmatch(value):
        raise ValueError(f"{name} is not a canonical identifier")


def _text(value: str, name: str) -> None:
    if not value.strip() or len(value) > 256 or "\x00" in value:
        raise ValueError(f"{name} is invalid")


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
        raise ValueError("remote execution timestamps must be timezone-aware")
