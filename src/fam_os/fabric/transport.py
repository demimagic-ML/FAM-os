"""Signed X25519 handshake and AES-GCM authenticated fabric channel."""

import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

FABRIC_TRANSPORT_CONTRACT_VERSION = "fam.fabric.transport/v1alpha1"


@dataclass(frozen=True, slots=True)
class FabricHandshake:
    device_id: str
    ephemeral_public_base64: str
    signature_base64: str


@dataclass(frozen=True, slots=True)
class FabricEncryptedEnvelope:
    session_id: str
    sequence: int
    nonce_base64: str
    ciphertext_base64: str
    contract_version: str = FABRIC_TRANSPORT_CONTRACT_VERSION


def create_handshake(device_id: str, signing_key: Ed25519PrivateKey, ephemeral_key):
    raw = ephemeral_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    signed = device_id.encode() + b"|" + raw
    return FabricHandshake(device_id, base64.b64encode(raw).decode(),
                           base64.b64encode(signing_key.sign(signed)).decode())


class FabricSecureChannel:
    def __init__(self, session_id, key):
        self._session_id, self._cipher, self._seen = session_id, AESGCM(key), set()

    @classmethod
    def establish(cls, session_id, local_ephemeral: X25519PrivateKey,
                  peer: FabricHandshake, trusted_peer_key_base64: str):
        raw = base64.b64decode(peer.ephemeral_public_base64, validate=True)
        Ed25519PublicKey.from_public_bytes(
            base64.b64decode(trusted_peer_key_base64, validate=True),
        ).verify(base64.b64decode(peer.signature_base64, validate=True),
                 peer.device_id.encode() + b"|" + raw)
        secret = local_ephemeral.exchange(X25519PublicKey.from_public_bytes(raw))
        key = HKDF(hashes.SHA256(), 32, None, session_id.encode()).derive(secret)
        return cls(session_id, key)

    def encrypt(self, sequence: int, payload: bytes):
        nonce = os.urandom(12)
        aad = f"{self._session_id}|{sequence}".encode()
        ciphertext = self._cipher.encrypt(nonce, payload, aad)
        return FabricEncryptedEnvelope(
            self._session_id, sequence, base64.b64encode(nonce).decode(),
            base64.b64encode(ciphertext).decode(),
        )

    def decrypt(self, envelope: FabricEncryptedEnvelope):
        if envelope.session_id != self._session_id or envelope.sequence in self._seen:
            raise ValueError("fabric envelope session mismatch or replay")
        aad = f"{self._session_id}|{envelope.sequence}".encode()
        value = self._cipher.decrypt(base64.b64decode(envelope.nonce_base64),
                                     base64.b64decode(envelope.ciphertext_base64), aad)
        self._seen.add(envelope.sequence)
        return value
