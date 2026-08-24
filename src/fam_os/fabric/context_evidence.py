"""Local requests and content-free evidence for minimum-context disclosure."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.fabric.context import (
    REMOTE_CONTEXT_CONTRACT_VERSION,
    RemoteContextReceipt,
    RemoteRawContextFragment,
    RemoteTaskDescriptor,
)
from fam_os.fabric.privacy import RemoteContextSensitivity


@dataclass(frozen=True, slots=True)
class RemoteContextSendRequest:
    request_id: str
    enrollment_id: str
    target_expert_id: str
    capability_declaration_id: str
    expected_privacy_revision: int
    purpose_id: str
    workspace_id: str
    sensitivity: RemoteContextSensitivity
    descriptor: RemoteTaskDescriptor
    raw_fragments: tuple[RemoteRawContextFragment, ...] = ()
    confirmed: bool = False
    contract_version: str = REMOTE_CONTEXT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value in (
            self.request_id, self.enrollment_id, self.target_expert_id,
            self.capability_declaration_id, self.purpose_id, self.workspace_id,
        ):
            if not value.strip():
                raise ValueError("remote context send identity is invalid")
        if self.expected_privacy_revision < 1:
            raise ValueError("remote context privacy revision is invalid")
        if not isinstance(self.sensitivity, RemoteContextSensitivity):
            raise TypeError("remote context sensitivity is invalid")
        if bool(self.raw_fragments) and not self.confirmed:
            raise PermissionError("raw remote context requires explicit confirmation")
        if self.contract_version != REMOTE_CONTEXT_CONTRACT_VERSION:
            raise ValueError("remote context contract is unsupported")


class RemoteContextDirection(StrEnum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


@dataclass(frozen=True, slots=True)
class RemoteContextDisclosureEvidence:
    evidence_id: str
    request_id: str
    request_sha256: str
    enrollment_id: str
    peer_device_id: str
    direction: RemoteContextDirection
    context_id: str
    target_expert_id: str
    purpose_id: str
    workspace_id: str
    sensitivity: RemoteContextSensitivity
    content_bytes: int
    content_sha256: str
    raw_fragment_sha256: tuple[str, ...]
    privacy_policy_revision: int | None
    capability_declaration_id: str | None
    receipt: RemoteContextReceipt
    reason_codes: tuple[str, ...]
    recorded_at: datetime
    local_only: bool = True
    contract_version: str = REMOTE_CONTEXT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value in (
            self.evidence_id, self.request_id, self.enrollment_id,
            self.peer_device_id, self.context_id, self.target_expert_id,
            self.purpose_id, self.workspace_id,
        ):
            if not value.strip():
                raise ValueError("remote context evidence identity is invalid")
        _digest(self.request_sha256, "remote context request")
        if not isinstance(self.direction, RemoteContextDirection):
            raise TypeError("remote context evidence direction is invalid")
        if not isinstance(self.sensitivity, RemoteContextSensitivity):
            raise TypeError("remote context evidence sensitivity is invalid")
        if self.content_bytes != self.receipt.content_bytes:
            raise ValueError("remote context evidence byte count differs from receipt")
        if self.content_sha256 != self.receipt.content_sha256:
            raise ValueError("remote context evidence digest differs from receipt")
        if len(self.raw_fragment_sha256) != self.receipt.raw_fragment_count:
            raise ValueError("remote context evidence fragment count differs from receipt")
        for value in self.raw_fragment_sha256:
            _digest(value, "remote context evidence fragment")
        outbound = self.direction is RemoteContextDirection.OUTBOUND
        if outbound != (self.privacy_policy_revision is not None):
            raise ValueError("only outbound context evidence binds local privacy revision")
        if outbound != (self.capability_declaration_id is not None):
            raise ValueError("only outbound context evidence binds capability selection")
        if not self.reason_codes:
            raise ValueError("remote context evidence needs reason codes")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("remote context evidence timestamp must be timezone-aware")
        if not self.local_only or self.contract_version != REMOTE_CONTEXT_CONTRACT_VERSION:
            raise ValueError("remote context evidence boundary is invalid")


def _digest(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} digest is invalid")
