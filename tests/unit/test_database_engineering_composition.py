import hashlib
import unittest

from cryptography.exceptions import InvalidTag

from fam_os.product.composition.database_engineering import (
    ProductDatabaseBackupProtector,
    compose_database_engineering,
)
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.keys import OwnerMasterKey


class AllowingAuthorizer:
    def authorize(self, request):
        raise AssertionError("not used by composition construction")


class DatabaseEngineeringCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        key = bytes(range(32))
        key_id = "owner-key-" + hashlib.sha256(key).hexdigest()[:24]
        self.protector = ProductDatabaseBackupProtector(
            "owner-1", ProductPayloadCipher(OwnerMasterKey(key_id, key)),
        )

    def test_backup_is_authenticated_and_bound_to_exact_context(self) -> None:
        ciphertext = self.protector.encrypt(b"sqlite bytes", "plan-1:target-1")
        self.assertNotIn(b"sqlite bytes", ciphertext)
        self.assertEqual(
            self.protector.decrypt(ciphertext, "plan-1:target-1"),
            b"sqlite bytes",
        )
        with self.assertRaises(InvalidTag):
            self.protector.decrypt(ciphertext, "plan-2:target-1")
        tampered = ciphertext[:-1] + bytes((ciphertext[-1] ^ 1,))
        with self.assertRaises((InvalidTag, ValueError)):
            self.protector.decrypt(tampered, "plan-1:target-1")

    def test_composition_returns_core_service_and_recovery_adapter(self) -> None:
        key = bytes(range(32))
        key_id = "owner-key-" + hashlib.sha256(key).hexdigest()[:24]
        unit = compose_database_engineering(
            "owner-1", ProductPayloadCipher(OwnerMasterKey(key_id, key)),
            AllowingAuthorizer(),
        )
        self.assertIsNotNone(unit.service)
        self.assertIsNotNone(unit.recovery)


if __name__ == "__main__":
    unittest.main()
