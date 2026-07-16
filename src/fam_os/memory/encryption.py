"""Owner-isolated AES-GCM encryption for persistent memory payloads."""

import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MEMORY_ENCRYPTION_CONTRACT_VERSION = "fam.memory.encryption/v1alpha1"


@dataclass(frozen=True, slots=True)
class MemoryEncryptionEvidence:
    evidence_id: str
    algorithm: str
    plaintext_absent: bool
    owner_round_trip: bool
    cross_owner_rejected: bool
    encrypted_database_sha256: str
    passed: bool
    contract_version: str = MEMORY_ENCRYPTION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        expected = self.plaintext_absent and self.owner_round_trip and self.cross_owner_rejected
        if self.algorithm != "AES-256-GCM" or self.passed != expected:
            raise ValueError("memory encryption evidence does not satisfy policy")
        if len(self.encrypted_database_sha256) != 64:
            raise ValueError("encrypted database digest must be SHA-256")


@dataclass(frozen=True, slots=True)
class OwnerMemoryKey:
    owner_id: str
    key_id: str
    key_bytes: bytes

    def __post_init__(self) -> None:
        if not self.owner_id.strip() or not self.key_id.strip() or len(self.key_bytes) != 32:
            raise ValueError("memory owner key requires IDs and 32 bytes")


class AesGcmMemoryCipher:
    def __init__(self, keys: tuple[OwnerMemoryKey, ...]) -> None:
        if not keys or len({item.owner_id for item in keys}) != len(keys):
            raise ValueError("memory cipher requires unique owner keys")
        self._keys = {item.owner_id: item for item in keys}

    def encrypt(self, owner_id: str, payload: bytes) -> str:
        key = self._key(owner_id)
        nonce = os.urandom(12)
        encrypted = AESGCM(key.key_bytes).encrypt(nonce, payload, owner_id.encode())
        return f"aesgcm:{key.key_id}:{base64.b64encode(nonce + encrypted).decode()}"

    def decrypt(self, owner_id: str, token: str) -> bytes:
        key = self._key(owner_id)
        prefix, key_id, encoded = token.split(":", 2)
        if prefix != "aesgcm" or key_id != key.key_id:
            raise ValueError("memory ciphertext key identity mismatch")
        raw = base64.b64decode(encoded, validate=True)
        return AESGCM(key.key_bytes).decrypt(raw[:12], raw[12:], owner_id.encode())

    def _key(self, owner_id: str) -> OwnerMemoryKey:
        try:
            return self._keys[owner_id]
        except KeyError as exc:
            raise PermissionError("no memory encryption key for owner") from exc
