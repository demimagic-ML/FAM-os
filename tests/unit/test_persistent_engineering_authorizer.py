import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.engineering_authority import PersistentEngineeringAuthorizer
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
    NOW,
    engineering_grant_schema_values,
)


class AcceptingOwnerVerifier:
    def verify_grant(self, approval, grant_sha256):
        return approval.grant_sha256 == grant_sha256

    def verify_break_glass(self, challenge, decision):
        return decision.challenge_id == challenge.challenge_id


class PersistentEngineeringAuthorizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
        storage = SecureStorage(
            database, OwnerKeyStore(root / "master.key", os.geteuid()),
        ).open()
        assert storage.database is not None and storage.cipher is not None
        self.database = storage.database
        self.repository = SqliteEngineeringGrantRepository(
            storage.database, storage.cipher, "owner-1",
        )
        (
            self.grant, self.approval, self.request, _authorization,
            self.challenge, self.break_glass, _execution,
        ) = engineering_grant_schema_values()

    def tearDown(self) -> None:
        self.database.close()
        self.temporary.cleanup()

    def test_owner_verified_activation_authorizes_and_audits(self) -> None:
        ids = iter(f"decision-{number}" for number in range(10))
        authorizer = PersistentEngineeringAuthorizer(
            self.repository, AcceptingOwnerVerifier(), lambda: NOW,
            lambda: next(ids),
        )
        authorizer.activate(
            self.grant, self.approval, self.challenge, self.break_glass,
        )
        decision = authorizer.authorize(self.request)
        self.assertTrue(decision.allowed)
        self.assertEqual(
            self.repository.decisions(self.grant.grant_id), (decision,),
        )

    def test_restart_state_denies_without_reactivation_and_audits(self) -> None:
        first = PersistentEngineeringAuthorizer(
            self.repository, AcceptingOwnerVerifier(), lambda: NOW,
        )
        first.activate(self.grant, self.approval, self.challenge, self.break_glass)
        self.repository.require_restart_reconfirmation()
        restarted = PersistentEngineeringAuthorizer(
            self.repository, AcceptingOwnerVerifier(), lambda: NOW,
        )
        decision = restarted.authorize(self.request)
        self.assertFalse(decision.allowed)
        self.assertIn("reconfirmation_required", decision.reason_code)
        self.assertEqual(len(self.repository.decisions(self.grant.grant_id)), 1)

    def test_invalid_owner_proof_has_no_persistent_effect(self) -> None:
        class Rejecting(AcceptingOwnerVerifier):
            def verify_grant(self, approval, grant_sha256):
                return False

        authorizer = PersistentEngineeringAuthorizer(
            self.repository, Rejecting(), lambda: NOW,
        )
        with self.assertRaisesRegex(PermissionError, "exact owner approval"):
            authorizer.activate(
                self.grant, self.approval, self.challenge, self.break_glass,
            )
        self.assertIsNone(self.repository.get(self.grant.grant_id))


if __name__ == "__main__":
    unittest.main()
