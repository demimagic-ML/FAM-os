"""Production composition for owner-key-protected candidate database work."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fam_os.adapters.database import (
    SQLiteDatabaseEngineeringAdapter,
    SQLiteDatabaseRecoveryAdapter,
)
from fam_os.core.engineering.database_service import (
    DatabaseEngineeringService,
    EngineeringDecisionAuthorizer,
)
from fam_os.product.storage.cipher import CipherContext, ProductPayloadCipher


class ProductDatabaseBackupProtector:
    def __init__(
        self,
        owner_id: str,
        cipher: ProductPayloadCipher,
        artifact_kind: str = "sqlite-snapshot",
    ) -> None:
        if not owner_id.strip():
            raise ValueError("database backup protector requires an owner identity")
        self._owner_id = owner_id
        self._cipher = cipher
        if not artifact_kind.strip():
            raise ValueError("database backup artifact kind is empty")
        self._artifact_kind = artifact_kind

    def encrypt(self, plaintext: bytes, context: str) -> bytes:
        token = self._cipher.encrypt(self._context(context), plaintext)
        return token.encode("ascii")

    def decrypt(self, ciphertext: bytes, context: str) -> bytes:
        token = ciphertext.decode("ascii", "strict")
        return self._cipher.decrypt(self._context(context), token)

    def _context(self, value: str) -> CipherContext:
        if not value.strip():
            raise ValueError("database backup context must be nonempty")
        identity = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return CipherContext(
            self._owner_id, "database-backup", identity, self._artifact_kind,
        )


@dataclass(frozen=True, slots=True)
class DatabaseEngineeringUnit:
    service: DatabaseEngineeringService
    recovery: SQLiteDatabaseRecoveryAdapter


def compose_database_engineering(
    owner_id: str,
    cipher: ProductPayloadCipher,
    authorizer: EngineeringDecisionAuthorizer,
) -> DatabaseEngineeringUnit:
    protector = ProductDatabaseBackupProtector(owner_id, cipher)
    executor = SQLiteDatabaseEngineeringAdapter(protector)
    recovery = SQLiteDatabaseRecoveryAdapter(protector)
    return DatabaseEngineeringUnit(
        DatabaseEngineeringService(authorizer, executor, recovery=recovery),
        recovery,
    )
