from datetime import datetime, timezone
import tempfile
import unittest
from pathlib import Path

import os

from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.engineering_secret_repository import SqliteEngineeringSecretRepository


NOW = datetime(2026, 7, 19, tzinfo=timezone.utc)


class EngineeringSecretRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.database = ProductionDatabase(StorageSettings(root / "state.db", os.geteuid()))
        opened = SecureStorage(
            self.database, OwnerKeyStore(root / "master.key", os.geteuid()),
        ).open()
        self.repository = SqliteEngineeringSecretRepository(
            self.database, opened.cipher, "owner",
        )

    def tearDown(self):
        self.database.close(); self.temporary.cleanup()

    def test_provision_rotate_resolve_delete_never_returns_plaintext_metadata(self):
        metadata = self.repository.provision(
            "secret.api", "API_TOKEN", "integration:api", "first", NOW,
        )
        self.assertNotIn("value", metadata)
        self.assertEqual({"API_TOKEN": "first"}, self.repository.environment(
            ("secret.api",), "integration:api",
        ))
        self.repository.rotate("secret.api", "second", NOW)
        self.assertEqual(2, self.repository.metadata("secret.api")["generation"])
        self.assertEqual({"API_TOKEN": "second"}, self.repository.environment(
            ("secret.api",), "integration:api",
        ))
        deleted = self.repository.delete("secret.api", NOW)
        self.assertEqual("deleted", deleted["state"])
        with self.assertRaises(KeyError):
            self.repository.environment(("secret.api",), "integration:api")
        self.assertEqual(
            ("provisioned", "rotated", "deleted"),
            tuple(item["action"] for item in self.repository.audit("secret.api")),
        )

    def test_consumer_collision_replay_and_ciphertext_tamper_fail_closed(self):
        self.repository.provision(
            "secret.api", "TOKEN", "integration:api", "protected", NOW,
        )
        with self.assertRaises(FileExistsError):
            self.repository.provision(
                "secret.api", "TOKEN", "integration:api", "again", NOW,
            )
        with self.assertRaises(PermissionError):
            self.repository.environment(("secret.api",), "integration:other")
        self.database.execute(
            "UPDATE engineering_secrets SET value_ciphertext='broken' WHERE secret_ref='secret.api'"
        )
        with self.assertRaises((ValueError, TypeError)):
            self.repository.environment(("secret.api",), "integration:api")


if __name__ == "__main__":
    unittest.main()
