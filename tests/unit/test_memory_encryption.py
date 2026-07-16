import sqlite3
import tempfile
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidTag

from fam_os.memory.encryption import AesGcmMemoryCipher, OwnerMemoryKey
from fam_os.memory.document_index import ApprovedDocumentIndex
from fam_os.memory.document_repository import SqliteDocumentIndexRepository
from tests.unit.test_approved_document_index import CONTENT, Runtime, approval


class MemoryEncryptionTests(unittest.TestCase):
    def test_owner_associated_data_rejects_cross_user_decryption(self):
        cipher = AesGcmMemoryCipher((OwnerMemoryKey("a", "key-a", b"a" * 32),
                                    OwnerMemoryKey("b", "key-b", b"a" * 32)))
        token = cipher.encrypt("a", b"private")
        self.assertEqual(b"private", cipher.decrypt("a", token))
        with self.assertRaises((ValueError, InvalidTag)):
            cipher.decrypt("b", token)

    def test_sqlite_contains_ciphertext_but_repository_recovers_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "encrypted.sqlite"
            cipher = AesGcmMemoryCipher((OwnerMemoryKey("owner", "key-1", b"k" * 32),))
            repository = SqliteDocumentIndexRepository(path, cipher)
            index = ApprovedDocumentIndex(repository, Runtime())
            index.index(approval(), CONTENT, ("GPU and CPU share work.", "Rain falls from clouds."))
            self.assertEqual("GPU and CPU share work.", repository.chunks("doc-1")[0][3])
            repository.close()
            raw = sqlite3.connect(path).execute("SELECT content,embedding FROM chunks").fetchall()
            self.assertTrue(all(value.startswith("aesgcm:") for row in raw for value in row))
            self.assertNotIn("GPU and CPU", path.read_bytes().decode("latin1"))


if __name__ == "__main__":
    unittest.main()
