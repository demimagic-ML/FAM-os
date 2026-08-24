"""Secure storage startup and explicit recovery-mode composition."""

from __future__ import annotations

import os
from pathlib import Path

from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.owner_identity import local_owner_id
from fam_os.product.engineering_authority import PersistentEngineeringAuthorizer
from fam_os.product.owner_engineering_authentication import (
    OwnerEngineeringAuthenticationRegistry,
    ProductOwnerAuthorityVerifier,
)
from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    SecureStorageResult,
    StorageSettings,
)


class ProductStorageUnit:
    def __init__(self, state_root: Path, owner_uid: int) -> None:
        self._state_root = state_root
        self._owner_uid = owner_uid
        state = state_root / "state"
        database = ProductionDatabase(StorageSettings(state / "fam.sqlite3", owner_uid))
        self._secure = SecureStorage(database, OwnerKeyStore(state / "master.key", owner_uid))
        self.result: SecureStorageResult | None = None
        self.core: CoreStorageComposition | None = None
        self.engineering_reconfirmations_required = 0
        self.engineering_authentication = None
        self.engineering_authorizer = None
        self.engineering_grants = None
        self.integration_environments = None
        self.engineering_secrets = None

    def start(self) -> SecureStorageResult:
        result = self._secure.open()
        self.result = result
        marker = self._state_root / "recovery/enabled"
        if result.recovery_required:
            marker.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            marker.write_text(result.reason + "\n", encoding="utf-8")
            os.chmod(marker, 0o600)
            return result
        marker.unlink(missing_ok=True)
        if result.database is None or result.cipher is None:
            raise RuntimeError("secure storage opened without required components")
        self.core = CoreStorageComposition(
            result.database, result.cipher, local_owner_id(self._owner_uid),
        )
        repositories = self.core.repositories()
        grants = repositories.engineering_grants
        self.engineering_grants = grants
        self.integration_environments = repositories.integration_environments
        self.engineering_secrets = repositories.engineering_secrets
        self.engineering_reconfirmations_required = grants.require_restart_reconfirmation()
        owner_id = local_owner_id(self._owner_uid)
        self.engineering_authentication = OwnerEngineeringAuthenticationRegistry(owner_id)
        self.engineering_authorizer = PersistentEngineeringAuthorizer(
            grants, ProductOwnerAuthorityVerifier(self.engineering_authentication),
        )
        return result

    def stop(self) -> None:
        if self.result is not None and self.result.database is not None:
            self.result.database.close()
