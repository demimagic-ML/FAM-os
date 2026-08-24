"""Device-signed content-free checkpoints for physical qualification."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.fabric.credentials import PersistentDeviceCredentials


PHYSICAL_PEER_OBSERVATION_VERSION = (
    "fam.fabric.physical-peer-observation/v1alpha1"
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


class PhysicalPeerCheckpoint(StrEnum):
    BEFORE_REMOTE_SUCCESS = "before_remote_success"
    AFTER_REMOTE_SUCCESS = "after_remote_success"
    BEFORE_PEER_LOSS = "before_peer_loss"
    AFTER_PEER_RESTART = "after_peer_restart"


@dataclass(frozen=True, slots=True)
class PhysicalPeerObservation:
    observation_id: str
    qualification_id: str
    checkpoint: PhysicalPeerCheckpoint
    device_id: str
    device_public_key_base64: str
    device_fingerprint_sha256: str
    context_evidence_count: int
    inspected_database_file_count: int
    prompt_sha256: str
    prompt_retained: bool
    captured_at: datetime
    signature_base64: str
    contract_version: str = PHYSICAL_PEER_OBSERVATION_VERSION

    def __post_init__(self) -> None:
        for identity_value in (
            self.observation_id, self.qualification_id, self.device_id,
        ):
            if (
                not isinstance(identity_value, str)
                or _ID.fullmatch(identity_value) is None
            ):
                raise ValueError("physical peer observation identity is invalid")
        if not isinstance(self.checkpoint, PhysicalPeerCheckpoint):
            raise TypeError("physical peer checkpoint is invalid")
        public = _public_key(self.device_public_key_base64)
        _digest(self.device_fingerprint_sha256)
        if (
            hashlib.sha256(public).hexdigest() != self.device_fingerprint_sha256
            or self.device_id != "device-" + self.device_fingerprint_sha256[:24]
        ):
            raise ValueError("physical peer device identity binding is invalid")
        for count in (
            self.context_evidence_count, self.inspected_database_file_count,
        ):
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError("physical peer observation count is invalid")
        _digest(self.prompt_sha256)
        if not isinstance(self.prompt_retained, bool):
            raise TypeError("physical peer prompt-retention evidence is invalid")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("physical peer observation time must be timezone-aware")
        _signature(self.signature_base64)
        if self.contract_version != PHYSICAL_PEER_OBSERVATION_VERSION:
            raise ValueError("physical peer observation contract is unsupported")


def create_physical_peer_observation(
    credentials: PersistentDeviceCredentials,
    *,
    observation_id: str,
    qualification_id: str,
    checkpoint: PhysicalPeerCheckpoint,
    context_evidence_count: int,
    inspected_database_file_count: int,
    prompt_sha256: str,
    prompt_retained: bool,
    captured_at: datetime,
) -> PhysicalPeerObservation:
    identity = credentials.identity
    values: dict[str, object] = {
        "observation_id": observation_id,
        "qualification_id": qualification_id,
        "checkpoint": checkpoint,
        "device_id": identity.device_id,
        "device_public_key_base64": identity.public_key_base64,
        "device_fingerprint_sha256": identity.fingerprint_sha256,
        "context_evidence_count": context_evidence_count,
        "inspected_database_file_count": inspected_database_file_count,
        "prompt_sha256": prompt_sha256,
        "prompt_retained": prompt_retained,
        "captured_at": captured_at,
    }
    signature = credentials.identity_key.sign(_payload(values))
    return PhysicalPeerObservation(
        observation_id=observation_id,
        qualification_id=qualification_id,
        checkpoint=checkpoint,
        device_id=identity.device_id,
        device_public_key_base64=identity.public_key_base64,
        device_fingerprint_sha256=identity.fingerprint_sha256,
        context_evidence_count=context_evidence_count,
        inspected_database_file_count=inspected_database_file_count,
        prompt_sha256=prompt_sha256,
        prompt_retained=prompt_retained,
        captured_at=captured_at,
        signature_base64=base64.b64encode(signature).decode("ascii"),
    )


def verify_physical_peer_observation(value: PhysicalPeerObservation) -> None:
    values = {
        name: getattr(value, name)
        for name in value.__dataclass_fields__
        if name not in {"signature_base64", "contract_version"}
    }
    try:
        Ed25519PublicKey.from_public_bytes(
            _public_key(value.device_public_key_base64),
        ).verify(
            base64.b64decode(value.signature_base64, validate=True),
            _payload(values),
        )
    except (InvalidSignature, TypeError, ValueError, binascii.Error) as error:
        raise ValueError("physical peer observation signature is invalid") from error


def _payload(values: dict[str, object]) -> bytes:
    def normalized(value):
        if isinstance(value, StrEnum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    return json.dumps({
        "contract_version": PHYSICAL_PEER_OBSERVATION_VERSION,
        **{name: normalized(value) for name, value in values.items()},
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _public_key(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, TypeError, ValueError) as error:
        raise ValueError("physical peer public key is invalid") from error
    if len(decoded) != 32:
        raise ValueError("physical peer public key is invalid")
    return decoded


def _signature(value: str) -> None:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, TypeError, ValueError) as error:
        raise ValueError("physical peer signature is invalid") from error
    if len(decoded) != 64:
        raise ValueError("physical peer signature is invalid")


def _digest(value: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("physical peer digest is invalid")
