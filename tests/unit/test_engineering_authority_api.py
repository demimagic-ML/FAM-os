import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fam_os.product.engineering_authority import PersistentEngineeringAuthorizer
from fam_os.product.engineering_authority_api import ProductEngineeringAuthorityApi
from fam_os.product.owner_engineering_authentication import (
    OwnerEngineeringAuthenticationRegistry,
    ProductOwnerAuthorityVerifier,
    break_glass_authentication_digest,
)
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.engineering_grant_repository import SqliteEngineeringGrantRepository
from fam_os.schemas import encode_document
from tests.contract.schema_engineering_fixtures import NOW, engineering_grant_schema_values


class EngineeringAuthorityApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        storage = SecureStorage(
            ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid())),
            OwnerKeyStore(root / "master.key", os.geteuid()),
        ).open()
        assert storage.database is not None and storage.cipher is not None
        self.database = storage.database
        self.repository = SqliteEngineeringGrantRepository(
            storage.database, storage.cipher, "owner-1",
        )
        values = engineering_grant_schema_values()
        self.grant, self.approval = values[0], values[1]
        self.challenge, self.decision = values[4], values[5]
        identifiers = iter(("grant-context", "break-context"))
        self.authentication = OwnerEngineeringAuthenticationRegistry(
            "owner-1", lambda: NOW, lambda: next(identifiers),
        )
        authorizer = PersistentEngineeringAuthorizer(
            self.repository, ProductOwnerAuthorityVerifier(self.authentication),
            lambda: NOW,
        )
        self.api = ProductEngineeringAuthorityApi(
            "owner-1", self.repository, self.authentication, authorizer,
        )

    def tearDown(self) -> None:
        self.database.close()
        self.temporary.cleanup()

    def test_exact_session_bound_contexts_activate_inspect_audit_and_revoke(self) -> None:
        session = "console-session-1"
        grant_context = self.api.issue_context({
            "owner_id": "owner-1", "purpose": "engineering-grant",
            "payload_sha256": self.approval.grant_sha256, "confirmed": True,
        }, session)
        break_digest = break_glass_authentication_digest(self.challenge, self.decision)
        break_context = self.api.issue_context({
            "owner_id": "owner-1", "purpose": "engineering-break-glass",
            "payload_sha256": break_digest, "confirmed": True,
        }, session)
        approval = replace(
            self.approval, authentication_context_id=grant_context["context_id"],
        )
        decision = replace(
            self.decision, authentication_context_id=break_context["context_id"],
        )
        activated = self.api.activate({
            "grant": encode_document(self.grant),
            "approval": encode_document(approval),
            "challenge": encode_document(self.challenge),
            "decision": encode_document(decision),
            "confirmed": True,
        }, session)
        self.assertTrue(activated["usable"])
        self.assertFalse(activated["reconfirmation_required"])
        self.assertEqual([], self.api.audit(self.grant.grant_id)["decisions"])
        revoked = self.api.revoke(self.grant.grant_id, {
            "owner_id": "owner-1", "confirmed": True,
        })
        self.assertFalse(revoked["usable"])
        self.assertEqual("revoked", revoked["grant"]["payload"]["state"])

    def test_activation_rejects_context_from_another_session(self) -> None:
        context = self.api.issue_context({
            "owner_id": "owner-1", "purpose": "engineering-grant",
            "payload_sha256": self.approval.grant_sha256, "confirmed": True,
        }, "console-session-1")
        approval = replace(
            self.approval, authentication_context_id=context["context_id"],
        )
        with self.assertRaisesRegex(PermissionError, "does not belong"):
            self.api.activate({
                "grant": encode_document(self.grant),
                "approval": encode_document(approval),
                "challenge": encode_document(self.challenge),
                "decision": encode_document(self.decision),
                "confirmed": True,
            }, "console-session-2")
        self.assertIsNone(self.repository.get(self.grant.grant_id))

    def test_false_confirmation_and_non_contract_payload_are_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            self.api.issue_context({
                "owner_id": "owner-1", "purpose": "engineering-grant",
                "payload_sha256": self.approval.grant_sha256, "confirmed": False,
            }, "console-session-1")
        with self.assertRaises(ValueError):
            self.api.activate({
                "grant": {}, "approval": encode_document(self.approval),
                "challenge": None, "decision": None, "confirmed": True,
            }, "console-session-1")


if __name__ == "__main__":
    unittest.main()
