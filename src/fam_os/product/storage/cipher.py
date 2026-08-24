"""AEAD encryption for durable sensitive product fields."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from fam_os.product.storage.keys import OwnerMasterKey


STORAGE_CIPHER_VERSION = "fam.storage.aes256gcm/v1"


@dataclass(frozen=True, slots=True)
class CipherContext:
    owner_id: str
    record_type: str
    record_id: str
    field_name: str

    def __post_init__(self) -> None:
        values = (self.owner_id, self.record_type, self.record_id, self.field_name)
        if any(not value.strip() or "\x00" in value for value in values):
            raise ValueError("cipher context values must be non-empty and canonical")

    def associated_data(self) -> bytes:
        return "\x00".join((STORAGE_CIPHER_VERSION, *self.__dict_values())).encode()

    def __dict_values(self) -> tuple[str, str, str, str]:
        return self.owner_id, self.record_type, self.record_id, self.field_name


class ProductPayloadCipher:
    def __init__(self, key: OwnerMasterKey) -> None:
        self._key = key
        self._cipher = AESGCM(key.key_bytes)

    def encrypt(self, context: CipherContext, plaintext: bytes) -> str:
        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(nonce, plaintext, context.associated_data())
        encoded = base64.b64encode(nonce + ciphertext).decode("ascii")
        return f"{STORAGE_CIPHER_VERSION}:{self._key.key_id}:{encoded}"

    def decrypt(self, context: CipherContext, token: str) -> bytes:
        version, key_id, encoded = token.split(":", 2)
        if version != STORAGE_CIPHER_VERSION or key_id != self._key.key_id:
            raise ValueError("ciphertext version or key identity mismatch")
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) < 29:
            raise ValueError("ciphertext is truncated")
        return self._cipher.decrypt(raw[:12], raw[12:], context.associated_data())
