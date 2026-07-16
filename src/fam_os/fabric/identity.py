"""Ed25519 device identity and explicit trust enrollment."""

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

DEVICE_IDENTITY_CONTRACT_VERSION = "fam.fabric.device-identity/v1alpha1"


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    device_id: str
    display_name: str
    public_key_base64: str
    fingerprint_sha256: str

    def __post_init__(self) -> None:
        raw = base64.b64decode(self.public_key_base64, validate=True)
        if len(raw) != 32 or hashlib.sha256(raw).hexdigest() != self.fingerprint_sha256:
            raise ValueError("device identity key or fingerprint is invalid")


@dataclass(frozen=True, slots=True)
class DeviceEnrollmentRequest:
    request_id: str
    identity: DeviceIdentity
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class DeviceEnrollmentChallenge:
    request_id: str
    nonce_base64: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class DeviceEnrollmentRecord:
    identity: DeviceIdentity
    enrolled_at: datetime
    owner_id: str
    trusted: bool
    contract_version: str = DEVICE_IDENTITY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.trusted or not self.owner_id.strip():
            raise ValueError("device enrollment must be explicit and owner-bound")


class DeviceEnrollmentAuthority:
    def enroll(self, request, challenge, signature_base64, owner_id, enrolled_at):
        if enrolled_at >= challenge.expires_at or challenge.request_id != request.request_id:
            raise ValueError("device enrollment challenge is mismatched or expired")
        key = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(request.identity.public_key_base64, validate=True),
        )
        key.verify(base64.b64decode(signature_base64, validate=True), _challenge_bytes(challenge))
        return DeviceEnrollmentRecord(request.identity, enrolled_at, owner_id, True)


def _challenge_bytes(challenge):
    return f"{challenge.request_id}|{challenge.nonce_base64}|{challenge.expires_at.isoformat()}".encode()
