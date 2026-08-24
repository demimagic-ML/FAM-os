"""Composition of key resolution, database binding, and payload cipher."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.database import ProductionDatabase
from fam_os.product.storage.keys import KeyResolutionState, OwnerKeyStore


@dataclass(frozen=True, slots=True)
class SecureStorageResult:
    recovery_required: bool
    reason: str
    database: ProductionDatabase | None
    cipher: ProductPayloadCipher | None

    def __post_init__(self) -> None:
        available = self.database is not None and self.cipher is not None
        if available == self.recovery_required:
            raise ValueError("secure storage result is inconsistent")


class SecureStorage:
    def __init__(self, database: ProductionDatabase, key_store: OwnerKeyStore) -> None:
        self._database = database
        self._key_store = key_store

    def open(self) -> SecureStorageResult:
        existed = self._database.settings.path.exists()
        resolution = self._key_store.resolve(database_exists=existed)
        if resolution.state is KeyResolutionState.RECOVERY_REQUIRED:
            return _recovery(resolution.reason)
        key = resolution.key
        if key is None:
            raise RuntimeError("ready key resolution did not return a key")
        self._database.open()
        if not _bind_key(self._database, key.key_id):
            self._database.close()
            return _recovery("master_key_does_not_match_database")
        return SecureStorageResult(
            False,
            resolution.reason,
            self._database,
            ProductPayloadCipher(key),
        )


def _bind_key(database: ProductionDatabase, key_id: str) -> bool:
    with database.transaction() as connection:
        row = connection.execute(
            "SELECT value FROM storage_metadata WHERE key='master_key_id'"
        ).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO storage_metadata(key,value) VALUES ('master_key_id',?)",
                (key_id,),
            )
            return True
        return row[0] == key_id


def _recovery(reason: str) -> SecureStorageResult:
    return SecureStorageResult(True, reason, None, None)
