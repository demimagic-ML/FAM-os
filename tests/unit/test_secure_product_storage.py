import os
import tempfile
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidTag

from fam_os.product.storage import (
    CipherContext,
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)


class SecureProductStorageTests(unittest.TestCase):
    def test_new_store_creates_key_binds_database_and_encrypts_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = _open(root)
            self.assertFalse(result.recovery_required)
            context = CipherContext("1000", "request", "request-1", "prompt")
            token = result.cipher.encrypt(context, b"private prompt")
            self.assertEqual(b"private prompt", result.cipher.decrypt(context, token))
            bound = result.database.execute(
                "SELECT value FROM storage_metadata WHERE key='master_key_id'"
            ).fetchone()[0]
            self.assertTrue(bound.startswith("owner-key-"))
            result.database.close()

    def test_missing_key_for_existing_database_enters_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = _open(root)
            initial.database.close()
            (root / "master.key").unlink()
            result = _open(root)
            self.assertTrue(result.recovery_required)
            self.assertEqual("master_key_missing_for_existing_database", result.reason)
            self.assertFalse((root / "master.key").exists())

    def test_corrupt_or_replaced_key_enters_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = _open(root)
            initial.database.close()
            key_path = root / "master.key"
            key_path.write_bytes(os.urandom(32))
            result = _open(root)
            self.assertTrue(result.recovery_required)
            self.assertEqual("master_key_does_not_match_database", result.reason)

            key_path.write_bytes(b"short")
            result = _open(root)
            self.assertTrue(result.recovery_required)
            self.assertEqual("master_key_corrupt_or_unsafe", result.reason)

    def test_ciphertext_is_bound_to_owner_record_and_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = _open(Path(temporary))
            original = CipherContext("1000", "request", "request-1", "prompt")
            token = result.cipher.encrypt(original, b"secret")
            changed = CipherContext("1000", "request", "request-2", "prompt")
            with self.assertRaises(InvalidTag):
                result.cipher.decrypt(changed, token)
            result.database.close()

    def test_plaintext_does_not_appear_in_database_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = _open(root)
            context = CipherContext("1000", "request", "request-1", "prompt")
            token = result.cipher.encrypt(context, b"unique private prompt")
            with result.database.transaction() as connection:
                connection.execute(
                    "INSERT INTO requests VALUES (?,?,?,?,?)",
                    ("request-1", token, "accepted", "now", "now"),
                )
            result.database.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            result.database.close()
            self.assertNotIn(b"unique private prompt", (root / "fam.sqlite3").read_bytes())


def _open(root: Path):
    database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
    return SecureStorage(database, OwnerKeyStore(root / "master.key", os.geteuid())).open()


if __name__ == "__main__":
    unittest.main()
