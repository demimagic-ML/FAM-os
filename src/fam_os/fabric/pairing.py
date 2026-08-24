"""Explicit owner-confirmed pairing for persistent FAM_OS device identities."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Mapping

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.fabric.credentials import PersistentDeviceCredentials
from fam_os.fabric.identity import DeviceIdentity
from fam_os.fabric.pairing_certificates import validate_identity_certificate

DEVICE_PAIRING_CONTRACT_VERSION = "fam.fabric.device-pairing/v1alpha1"


@dataclass(frozen=True, slots=True)
class PeerEndpoint:
    host: str
    port: int

    def __post_init__(self) -> None:
        if (
            not 1 <= len(self.host) <= 253
            or any(character.isspace() or ord(character) < 33 for character in self.host)
            or not 1 <= self.port <= 65535
        ):
            raise ValueError("peer endpoint is invalid")


@dataclass(frozen=True, slots=True)
class DevicePairingOffer:
    request_id: str
    identity: DeviceIdentity
    identity_certificate_base64: str
    endpoint: PeerEndpoint
    nonce_base64: str
    created_at: datetime
    expires_at: datetime
    signature_base64: str
    contract_version: str = DEVICE_PAIRING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "pairing request", 128)
        _aware(self.created_at, "pairing creation")
        _aware(self.expires_at, "pairing expiry")
        nonce = base64.b64decode(self.nonce_base64, validate=True)
        if len(nonce) != 32 or self.expires_at <= self.created_at:
            raise ValueError("pairing offer nonce or lifetime is invalid")
        if self.expires_at - self.created_at > timedelta(minutes=15):
            raise ValueError("pairing offer lifetime exceeds the hard limit")
        if self.contract_version != DEVICE_PAIRING_CONTRACT_VERSION:
            raise ValueError("pairing offer contract is unsupported")


@dataclass(frozen=True, slots=True)
class DevicePairingApproval:
    approval_id: str
    owner_id: str
    local_identity: DeviceIdentity
    peer_identity: DeviceIdentity
    peer_identity_certificate_base64: str
    peer_endpoint: PeerEndpoint
    local_offer_id: str
    peer_offer_id: str
    ceremony_sha256: str
    approved_at: datetime
    signature_base64: str
    contract_version: str = DEVICE_PAIRING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value, label in (
            (self.approval_id, "approval"), (self.owner_id, "owner"),
            (self.local_identity.device_id, "local device"), (self.local_offer_id, "local offer"),
            (self.peer_offer_id, "peer offer"),
        ):
            _text(value, label, 128)
        if len(self.ceremony_sha256) != 64:
            raise ValueError("pairing ceremony digest is invalid")
        int(self.ceremony_sha256, 16)
        _aware(self.approved_at, "approval")
        if self.local_identity.device_id == self.peer_identity.device_id:
            raise ValueError("a device cannot approve itself")
        if self.contract_version != DEVICE_PAIRING_CONTRACT_VERSION:
            raise ValueError("pairing approval contract is unsupported")

    @property
    def local_device_id(self) -> str:
        return self.local_identity.device_id


def create_pairing_offer(
    credentials: PersistentDeviceCredentials,
    endpoint: PeerEndpoint,
    *,
    created_at: datetime | None = None,
    lifetime: timedelta = timedelta(minutes=10),
    request_id: str | None = None,
) -> DevicePairingOffer:
    created = created_at or datetime.now(UTC)
    if lifetime <= timedelta(0) or lifetime > timedelta(minutes=15):
        raise ValueError("pairing offer lifetime is invalid")
    unsigned = DevicePairingOffer(
        request_id or "pair-" + os.urandom(16).hex(), credentials.identity,
        credentials.identity_certificate_base64, endpoint,
        base64.b64encode(os.urandom(32)).decode("ascii"), created, created + lifetime, "",
    )
    signature = credentials.identity_key.sign(_offer_payload(unsigned))
    return _offer_with_signature(unsigned, base64.b64encode(signature).decode("ascii"))


def verify_pairing_offer(offer: DevicePairingOffer, *, observed_at: datetime) -> x509.Certificate:
    _aware(observed_at, "pairing observation")
    if observed_at < offer.created_at - timedelta(minutes=2) or observed_at >= offer.expires_at:
        raise ValueError("pairing offer is not currently valid")
    try:
        certificate = validate_identity_certificate(
            offer.identity, offer.identity_certificate_base64, observed_at=observed_at,
        )
        public = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(offer.identity.public_key_base64, validate=True),
        )
        public.verify(base64.b64decode(offer.signature_base64, validate=True), _offer_payload(offer))
    except (InvalidSignature, TypeError, ValueError) as error:
        raise ValueError("pairing offer trust proof is invalid") from error
    return certificate


def pairing_code(local: DevicePairingOffer, peer: DevicePairingOffer) -> str:
    if local.identity.device_id == peer.identity.device_id:
        raise ValueError("pairing requires two different device identities")
    digest = bytes.fromhex(_ceremony_digest(local, peer))
    digits = f"{int.from_bytes(digest[:8], 'big') % 1_000_000_000_000:012d}"
    return "-".join((digits[:4], digits[4:8], digits[8:]))


def confirm_pairing(
    credentials: PersistentDeviceCredentials,
    local: DevicePairingOffer,
    peer: DevicePairingOffer,
    displayed_code: str,
    *,
    owner_id: str,
    approved_at: datetime | None = None,
) -> DevicePairingApproval:
    approved = approved_at or datetime.now(UTC)
    _text(owner_id, "owner", 128)
    if local.identity != credentials.identity:
        raise ValueError("local pairing offer does not belong to this device")
    verify_pairing_offer(local, observed_at=approved)
    verify_pairing_offer(peer, observed_at=approved)
    expected = pairing_code(local, peer)
    if not hmac.compare_digest(expected, displayed_code):
        raise PermissionError("pairing confirmation code does not match")
    ceremony = _ceremony_digest(local, peer)
    approval_id = "peer-approval-" + hashlib.sha256(
        f"{credentials.identity.device_id}|{peer.identity.device_id}|{ceremony}".encode(),
    ).hexdigest()[:32]
    unsigned = DevicePairingApproval(
        approval_id, owner_id, credentials.identity, peer.identity,
        peer.identity_certificate_base64, peer.endpoint, local.request_id,
        peer.request_id, ceremony, approved, "",
    )
    signature = credentials.identity_key.sign(_approval_payload(unsigned))
    return _approval_with_signature(unsigned, base64.b64encode(signature).decode("ascii"))


def verify_pairing_approval(
    approval: DevicePairingApproval,
    local_identity: DeviceIdentity,
) -> None:
    if approval.local_identity != local_identity:
        raise ValueError("pairing approval belongs to a different local device")
    public = Ed25519PublicKey.from_public_bytes(
        base64.b64decode(local_identity.public_key_base64, validate=True),
    )
    public.verify(
        base64.b64decode(approval.signature_base64, validate=True),
        _approval_payload(approval),
    )
    validate_identity_certificate(
        approval.peer_identity, approval.peer_identity_certificate_base64,
        observed_at=approval.approved_at,
    )


def pairing_offer_document(offer: DevicePairingOffer) -> dict[str, object]:
    return {
        "contract_version": offer.contract_version,
        "request_id": offer.request_id,
        "identity": _identity_document(offer.identity),
        "identity_certificate_base64": offer.identity_certificate_base64,
        "endpoint": {"host": offer.endpoint.host, "port": offer.endpoint.port},
        "nonce_base64": offer.nonce_base64,
        "created_at": offer.created_at.isoformat(),
        "expires_at": offer.expires_at.isoformat(),
        "signature_base64": offer.signature_base64,
    }


def _offer_payload(offer: DevicePairingOffer) -> bytes:
    document = pairing_offer_document(offer)
    document.pop("signature_base64")
    return _canonical(document)


def _approval_payload(approval: DevicePairingApproval) -> bytes:
    document = {
        "contract_version": approval.contract_version,
        "approval_id": approval.approval_id,
        "owner_id": approval.owner_id,
        "local_identity": _identity_document(approval.local_identity),
        "peer_identity": _identity_document(approval.peer_identity),
        "peer_identity_certificate_base64": approval.peer_identity_certificate_base64,
        "peer_endpoint": {"host": approval.peer_endpoint.host, "port": approval.peer_endpoint.port},
        "local_offer_id": approval.local_offer_id,
        "peer_offer_id": approval.peer_offer_id,
        "ceremony_sha256": approval.ceremony_sha256,
        "approved_at": approval.approved_at.isoformat(),
    }
    return _canonical(document)


def _ceremony_digest(local: DevicePairingOffer, peer: DevicePairingOffer) -> str:
    ordered = sorted((_offer_payload(local), _offer_payload(peer)))
    return hashlib.sha256(ordered[0] + b"|" + ordered[1]).hexdigest()


def _offer_with_signature(offer: DevicePairingOffer, signature: str) -> DevicePairingOffer:
    return DevicePairingOffer(
        offer.request_id, offer.identity, offer.identity_certificate_base64,
        offer.endpoint, offer.nonce_base64, offer.created_at, offer.expires_at, signature,
    )


def _approval_with_signature(
    approval: DevicePairingApproval, signature: str,
) -> DevicePairingApproval:
    return DevicePairingApproval(
        approval.approval_id, approval.owner_id, approval.local_identity,
        approval.peer_identity, approval.peer_identity_certificate_base64,
        approval.peer_endpoint, approval.local_offer_id, approval.peer_offer_id,
        approval.ceremony_sha256, approval.approved_at, signature,
    )


def _identity_document(identity: DeviceIdentity) -> dict[str, str]:
    return {
        "device_id": identity.device_id, "display_name": identity.display_name,
        "public_key_base64": identity.public_key_base64,
        "fingerprint_sha256": identity.fingerprint_sha256,
    }


def _canonical(document: Mapping[str, object]) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _text(value: str, label: str, maximum: int) -> None:
    if not 1 <= len(value.strip()) <= maximum or any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} identity is invalid")


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} timestamp must be timezone-aware")
