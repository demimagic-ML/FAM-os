"""Narrow pre-execution control protocol for authenticated peer health."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.fabric.peer_state import PeerCapabilityDeclaration
from fam_os.fabric.context import RemoteContextEnvelope, RemoteContextReceipt

PEER_CONTROL_CONTRACT_VERSION = "fam.fabric.peer-control/v1alpha1"


class PeerControlOperation(StrEnum):
    HEALTH = "health"
    DESCRIBE = "describe"
    CONTEXT = "context"


class PeerControlStatus(StrEnum):
    READY = "ready"


@dataclass(frozen=True, slots=True)
class PeerControlRequest:
    request_id: str
    sender_device_id: str
    operation: PeerControlOperation
    issued_at: datetime
    context: RemoteContextEnvelope | None = None
    contract_version: str = PEER_CONTROL_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.sender_device_id.strip():
            raise ValueError("peer control request identity is invalid")
        if self.issued_at.tzinfo is None or self.issued_at.utcoffset() is None:
            raise ValueError("peer control request timestamp must be timezone-aware")
        if (self.operation is PeerControlOperation.CONTEXT) != (self.context is not None):
            raise ValueError("peer control context does not match operation")
        if self.contract_version != PEER_CONTROL_CONTRACT_VERSION:
            raise ValueError("peer control request contract is unsupported")


@dataclass(frozen=True, slots=True)
class PeerControlResponse:
    request_id: str
    responder_device_id: str
    status: PeerControlStatus
    observed_at: datetime
    peer_certificate_sha256: str
    capabilities: tuple[PeerCapabilityDeclaration, ...] = ()
    context_receipt: RemoteContextReceipt | None = None
    contract_version: str = PEER_CONTROL_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.responder_device_id.strip():
            raise ValueError("peer control response identity is invalid")
        if len(self.peer_certificate_sha256) != 64:
            raise ValueError("peer control certificate evidence is invalid")
        int(self.peer_certificate_sha256, 16)
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("peer control response timestamp must be timezone-aware")
        if self.status is PeerControlStatus.READY and any(
            item.device_id != self.responder_device_id for item in self.capabilities
        ):
            raise ValueError("peer control capabilities belong to another device")
        if self.capabilities and self.context_receipt is not None:
            raise ValueError("peer control response cannot mix description and context receipt")
        if self.contract_version != PEER_CONTROL_CONTRACT_VERSION:
            raise ValueError("peer control response contract is unsupported")
