import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)
from fam_os.product.storage.engineering_grant_repository import (
    SqliteEngineeringGrantRepository,
)
from tests.contract.schema_engineering_fixtures import (
    engineering_grant_schema_values,
)


class EngineeringGrantRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        database = ProductionDatabase(
            StorageSettings(root / "fam.sqlite3", os.geteuid()),
        )
        storage = SecureStorage(
            database, OwnerKeyStore(root / "master.key", os.geteuid()),
        ).open()
        assert storage.database is not None and storage.cipher is not None
        self.database = storage.database
        self.repository = SqliteEngineeringGrantRepository(
            storage.database, storage.cipher, "owner-1",
        )
        (
            self.grant, self.approval, _request, self.decision,
            _challenge, _break_glass, _execution,
        ) = engineering_grant_schema_values()

    def tearDown(self) -> None:
        self.database.close()
        self.temporary.cleanup()

    def test_restart_requires_owner_reconfirmation_before_use(self) -> None:
        self.repository.put(self.grant, self.approval)
        stored = self.repository.get(self.grant.grant_id)
        self.assertIsNotNone(stored)
        self.assertTrue(stored[2])
        self.assertIsNone(self.repository.usable(self.grant.grant_id))
        self.assertTrue(self.repository.mark_reconfirmed(self.grant.grant_id))
        self.assertEqual(self.repository.usable(self.grant.grant_id), self.grant)
        self.assertEqual(self.repository.require_restart_reconfirmation(), 1)
        self.assertIsNone(self.repository.usable(self.grant.grant_id))

    def test_authorization_audit_is_encrypted_ordered_and_replay_safe(self) -> None:
        self.repository.put(self.grant, self.approval)
        self.repository.record_decision(self.decision)
        self.assertEqual(self.repository.decisions(self.grant.grant_id), (self.decision,))
        with self.assertRaises(Exception):
            self.repository.record_decision(self.decision)
        row = self.database.fetchone(
            "SELECT decision_ciphertext FROM engineering_authorization_audit "
            "WHERE decision_id=?", (self.decision.decision_id,),
        )
        self.assertNotIn(self.decision.reason_code, row[0])


if __name__ == "__main__":
    unittest.main()
