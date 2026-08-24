"""Signed peer capabilities and locally measured trust-state evidence."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.experts.capabilities import require_expert_capabilities
from fam_os.fabric.credentials import PersistentDeviceCredentials
from fam_os.fabric.identity import DeviceIdentity
from fam_os.fabric.privacy import RemotePrivacyPolicy

PEER_STATE_CONTRACT_VERSION = "fam.fabric.peer-state/v1alpha1"
PEER_EXPERT_TIERS = frozenset({
    "economical", "specialist", "escalation", "embedding",
})


@dataclass(frozen=True, slots=True)
class PeerCapabilityDeclaration:
    declaration_id: str
    device_id: str
    expert_id: str
    model_ref: str
    expert_tier: str
    capability_ids: tuple[str, ...]
    maximum_context_bytes: int
    manifest_sha256: str
    revision: int
    issued_at: datetime
    expires_at: datetime
    signature_base64: str
    contract_version: str = PEER_STATE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value, name in (
            (self.declaration_id, "declaration"), (self.device_id, "device"),
            (self.expert_id, "expert"), (self.model_ref, "model"),
        ):
            _text(value, name)
        if self.expert_tier not in PEER_EXPERT_TIERS:
            raise ValueError("peer capability expert tier is invalid")
        require_expert_capabilities(self.capability_ids)
        if self.maximum_context_bytes <= 0 or self.revision < 1:
            raise ValueError("peer capability limits or revision are invalid")
        _digest(self.manifest_sha256, "peer capability manifest")
        _time(self.issued_at)
        _time(self.expires_at)
        if self.expires_at <= self.issued_at:
            raise ValueError("peer capability declaration lifetime is invalid")
        if self.contract_version != PEER_STATE_CONTRACT_VERSION:
            raise ValueError("peer state contract is unsupported")


@dataclass(frozen=True, slots=True)
class PeerPerformanceObservation:
    observation_id: str
    enrollment_id: str
    peer_device_id: str
    round_trip_milliseconds: float
    response_bytes: int
    observed_at: datetime
    peer_certificate_sha256: str
    tls_version: str = "TLSv1.3"
    source: str = "local_authenticated_probe"
    contract_version: str = PEER_STATE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value, name in (
            (self.observation_id, "observation"),
            (self.enrollment_id, "enrollment"),
            (self.peer_device_id, "peer device"),
        ):
            _text(value, name)
        if not 0 <= self.round_trip_milliseconds <= 300_000:
            raise ValueError("peer round-trip measurement is invalid")
        if not 1 <= self.response_bytes <= 1_048_576:
            raise ValueError("peer response measurement is invalid")
        _time(self.observed_at)
        _digest(self.peer_certificate_sha256, "peer performance certificate")
        if self.tls_version != "TLSv1.3":
            raise ValueError("peer performance TLS version is invalid")
        if self.source != "local_authenticated_probe":
            raise ValueError("peer performance evidence must be locally measured")
        if self.contract_version != PEER_STATE_CONTRACT_VERSION:
            raise ValueError("peer state contract is unsupported")


@dataclass(frozen=True, slots=True)
class PeerPrivacyPolicyRecord:
    enrollment_id: str
    peer_device_id: str
    policy: RemotePrivacyPolicy
    revision: int
    updated_at: datetime
    contract_version: str = PEER_STATE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.enrollment_id, "enrollment")
        _text(self.peer_device_id, "peer device")
        if self.revision < 1:
            raise ValueError("peer privacy revision is invalid")
        if self.policy.allowed_device_ids != (self.peer_device_id,):
            raise ValueError("peer privacy policy must bind exactly one peer")
        _time(self.updated_at)
        if self.contract_version != PEER_STATE_CONTRACT_VERSION:
            raise ValueError("peer state contract is unsupported")


class PeerManagementOperation(StrEnum):
    REVOKE = "revoke"
    SET_PRIVACY = "set_privacy"


@dataclass(frozen=True, slots=True)
class PeerManagementRequest:
    request_id: str
    owner_id: str
    operation: PeerManagementOperation
    enrollment_id: str
    expected_revision: int
    confirmed: bool
    reason_code: str
    privacy_policy: RemotePrivacyPolicy | None = None
    contract_version: str = PEER_STATE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value, name in (
            (self.request_id, "request"), (self.owner_id, "owner"),
            (self.enrollment_id, "enrollment"), (self.reason_code, "reason"),
        ):
            _text(value, name)
        if self.expected_revision < 0 or not isinstance(self.confirmed, bool):
            raise ValueError("peer management revision or confirmation is invalid")
        privacy = self.operation is PeerManagementOperation.SET_PRIVACY
        if privacy != (self.privacy_policy is not None):
            raise ValueError("peer management payload does not match operation")
        if self.contract_version != PEER_STATE_CONTRACT_VERSION:
            raise ValueError("peer state contract is unsupported")


@dataclass(frozen=True, slots=True)
class PeerManagementReceipt:
    receipt_id: str
    request_id: str
    owner_id: str
    operation: PeerManagementOperation
    enrollment_id: str
    request_sha256: str
    before_revision: int
    resulting_revision: int
    applied: bool
    reason_codes: tuple[str, ...]
    recorded_at: datetime
    local_only: bool = True
    contract_version: str = PEER_STATE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value, name in (
            (self.receipt_id, "receipt"), (self.request_id, "request"),
            (self.owner_id, "owner"), (self.enrollment_id, "enrollment"),
        ):
            _text(value, name)
        _digest(self.request_sha256, "peer management request")
        if self.before_revision < 0 or self.resulting_revision < self.before_revision:
            raise ValueError("peer management receipt revision is invalid")
        if self.applied != (self.resulting_revision == self.before_revision + 1):
            raise ValueError("peer management receipt transition is inconsistent")
        if not self.reason_codes or len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("peer management receipt needs unique reason codes")
        _time(self.recorded_at)
        if not self.local_only or self.contract_version != PEER_STATE_CONTRACT_VERSION:
            raise ValueError("peer management receipt boundary is invalid")


def create_capability_declaration(
    credentials: PersistentDeviceCredentials, *, declaration_id: str,
    expert_id: str, model_ref: str, expert_tier: str,
    capability_ids: tuple[str, ...],
    maximum_context_bytes: int, manifest_sha256: str, revision: int,
    issued_at: datetime, expires_at: datetime,
) -> PeerCapabilityDeclaration:
    unsigned = PeerCapabilityDeclaration(
        declaration_id, credentials.identity.device_id, expert_id, model_ref,
        expert_tier, capability_ids, maximum_context_bytes, manifest_sha256, revision,
        issued_at, expires_at, "",
    )
    signature = credentials.identity_key.sign(_capability_payload(unsigned))
    return PeerCapabilityDeclaration(
        unsigned.declaration_id, unsigned.device_id, unsigned.expert_id,
        unsigned.model_ref, unsigned.expert_tier, unsigned.capability_ids,
        unsigned.maximum_context_bytes,
        unsigned.manifest_sha256, unsigned.revision, unsigned.issued_at,
        unsigned.expires_at, base64.b64encode(signature).decode("ascii"),
    )


def verify_capability_declaration(
    value: PeerCapabilityDeclaration, identity: DeviceIdentity, observed_at: datetime,
) -> None:
    if value.device_id != identity.device_id or not value.issued_at <= observed_at < value.expires_at:
        raise ValueError("peer capability identity or validity is invalid")
    try:
        public = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(identity.public_key_base64, validate=True),
        )
        public.verify(
            base64.b64decode(value.signature_base64, validate=True),
            _capability_payload(value),
        )
    except (InvalidSignature, TypeError, ValueError) as error:
        raise ValueError("peer capability signature is invalid") from error


def _capability_payload(value: PeerCapabilityDeclaration) -> bytes:
    document = {
        "contract_version": value.contract_version,
        "declaration_id": value.declaration_id, "device_id": value.device_id,
        "expert_id": value.expert_id, "model_ref": value.model_ref,
        "expert_tier": value.expert_tier,
        "capability_ids": value.capability_ids,
        "maximum_context_bytes": value.maximum_context_bytes,
        "manifest_sha256": value.manifest_sha256, "revision": value.revision,
        "issued_at": value.issued_at.isoformat(), "expires_at": value.expires_at.isoformat(),
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def _text(value: str, name: str) -> None:
    if not 1 <= len(value.strip()) <= 256:
        raise ValueError(f"{name} identity is invalid")


def _digest(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} digest is invalid")


def _time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("peer state timestamps must be timezone-aware")
