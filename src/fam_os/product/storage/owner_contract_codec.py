"""Owner-bound encryption codecs for standalone durable stores."""

import json

from fam_os.product.storage.contract_payload import decrypt_contract, encrypt_contract
from fam_os.product.storage.cipher import CipherContext


class OwnerBoundContractCodec:
    def __init__(self, cipher, owner_id: str, kind: str, expected_type) -> None:
        self._cipher = cipher
        self._owner_id = owner_id
        self._kind = kind
        self._expected_type = expected_type

    def encode(self, identity: str, value) -> str:
        return encrypt_contract(
            self._cipher, self._owner_id, self._kind, identity, value,
        )

    def decode(self, identity: str, token: str):
        return decrypt_contract(
            self._cipher, self._owner_id, self._kind, identity, token,
            self._expected_type,
        )


class OwnerBoundJsonCodec:
    """AEAD-protect a versioned internal JSON record with owner-bound AAD."""

    def __init__(self, cipher, owner_id: str, kind: str) -> None:
        self._cipher = cipher
        self._owner_id = owner_id
        self._kind = kind

    def encode(self, identity: str, value: dict) -> str:
        if not isinstance(value, dict):
            raise TypeError("owner-bound JSON value must be an object")
        serialized = json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        return self._cipher.encrypt(self._context(identity), serialized)

    def decode(self, identity: str, token: str) -> dict:
        value = json.loads(
            self._cipher.decrypt(self._context(identity), token).decode("utf-8")
        )
        if not isinstance(value, dict):
            raise TypeError("owner-bound JSON value is not an object")
        return value

    def _context(self, identity: str) -> CipherContext:
        return CipherContext(self._owner_id, self._kind, identity, "json-record")
