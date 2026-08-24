import os
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from tests.contract.schema_application_fixtures import NOW, permission_grant


class ApplicationPermissionRepositoryTests(unittest.TestCase):
    def test_grants_are_encrypted_queryable_and_revocable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
            opened = SecureStorage(
                database, OwnerKeyStore(root / "master.key", os.geteuid()),
            ).open()
            repository = CoreStorageComposition(
                database, opened.cipher, str(os.geteuid()),
            ).repositories().application_permissions
            grant = replace(permission_grant(), expires_at=NOW + timedelta(hours=1))
            repository.put(grant)
            self.assertEqual(grant, repository.get(grant.grant_id))
            self.assertEqual((grant,), repository.active(grant.subject_id, NOW))
            self.assertEqual(1, repository.active_count(NOW))
            self.assertEqual(0, repository.active_count(NOW + timedelta(hours=2)))
            raw = database.fetchone(
                "SELECT payload_ciphertext FROM application_permissions WHERE grant_id=?",
                (grant.grant_id,),
            )[0]
            self.assertNotIn(grant.subject_id, raw)
            self.assertTrue(repository.revoke(grant.grant_id, NOW + timedelta(minutes=1)))
            self.assertEqual((), repository.active(grant.subject_id, NOW + timedelta(minutes=2)))
            self.assertEqual(0, repository.active_count(NOW + timedelta(minutes=2)))
            database.close()


if __name__ == "__main__":
    unittest.main()
