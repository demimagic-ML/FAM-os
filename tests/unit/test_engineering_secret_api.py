from datetime import datetime, timezone
import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.engineering_secret_api import (
    ProductEngineeringSecretApi, engineering_secret_operation_digest,
)
from fam_os.product.engineering_secret_lifecycle import (
    EngineeringSecretLifecycleCoordinator,
    UnavailableIntegrationEnvironmentLifecycle,
)
from fam_os.product.owner_engineering_authentication import OwnerEngineeringAuthenticationRegistry
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.engineering_secret_repository import SqliteEngineeringSecretRepository


NOW = datetime(2026, 7, 19, tzinfo=timezone.utc)


class EngineeringSecretApiTests(unittest.TestCase):
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
        self.authentication = OwnerEngineeringAuthenticationRegistry("owner", clock=lambda: NOW)
        self.environments = RecordingEnvironments(())
        self.api = ProductEngineeringSecretApi(
            "owner", self.repository, self.authentication, clock=lambda: NOW,
            lifecycle=EngineeringSecretLifecycleCoordinator(),
            environments=self.environments,
        )

    def tearDown(self):
        self.database.close(); self.temporary.cleanup()

    def test_exact_single_use_session_context_controls_metadata_only_lifecycle(self):
        provision = self._document(
            "provision", "engineering-secret-provision", "first",
            tool_key="API_TOKEN", consumer_id="integration:api",
        )
        metadata = self.api.provision(provision, "session")
        self.assertNotIn("value", metadata)
        with self.assertRaises(PermissionError):
            self.api.provision(provision, "session")

        rotate = self._document("rotate", "engineering-secret-rotate", "second")
        self.assertEqual(2, self.api.rotate(rotate, "session")["generation"])
        delete = self._document("delete", "engineering-secret-delete", "")
        self.assertEqual("deleted", self.api.delete(delete, "session")["state"])
        self.assertEqual(3, len(self.api.audit("secret.api")["events"]))
        self.assertNotIn("value", str(self.api.list()))

    def test_wrong_session_digest_confirmation_owner_and_unknown_fields_fail(self):
        document = self._document(
            "provision", "engineering-secret-provision", "first",
            tool_key="API_TOKEN", consumer_id="integration:api",
        )
        for change, error in (
            ({"confirmed": False}, PermissionError),
            ({"owner_id": "other"}, PermissionError),
            ({"value": "tampered"}, PermissionError),
        ):
            with self.subTest(change=change), self.assertRaises(error):
                self.api.provision(document | change, "session")
        with self.assertRaises(PermissionError):
            self.api.provision(document, "other-session")
        with self.assertRaises(ValueError):
            self.api.provision(document | {"extra": True}, "session")
        self.assertEqual("active", self.api.provision(document, "session")["state"])

    def test_rotate_drains_only_exact_active_reference_before_commit(self):
        self.api.provision(self._document(
            "provision", "engineering-secret-provision", "first",
            tool_key="API_TOKEN", consumer_id="integration:api",
        ), "session")
        environments = RecordingEnvironments((
            StoredEnvironment("matching", "secret.api"),
            StoredEnvironment("other", "secret.other"),
        ))
        api = ProductEngineeringSecretApi(
            "owner", self.repository, self.authentication, clock=lambda: NOW,
            lifecycle=EngineeringSecretLifecycleCoordinator(),
            environments=environments,
        )
        metadata = api.rotate(
            self._document("rotate", "engineering-secret-rotate", "second"),
            "session",
        )
        self.assertEqual(2, metadata["generation"])
        self.assertEqual(["matching"], environments.cleaned)

    def test_failed_cleanup_prevents_secret_delete_commit(self):
        self.api.provision(self._document(
            "provision", "engineering-secret-provision", "first",
            tool_key="API_TOKEN", consumer_id="integration:api",
        ), "session")
        environments = RecordingEnvironments(
            (StoredEnvironment("matching", "secret.api"),), fail=True,
        )
        api = ProductEngineeringSecretApi(
            "owner", self.repository, self.authentication, clock=lambda: NOW,
            lifecycle=EngineeringSecretLifecycleCoordinator(),
            environments=environments,
        )
        with self.assertRaisesRegex(RuntimeError, "cleanup failed"):
            api.delete(
                self._document("delete", "engineering-secret-delete", ""),
                "session",
            )
        self.assertEqual("active", self.repository.metadata("secret.api")["state"])
        self.assertEqual(1, self.repository.metadata("secret.api")["generation"])

    def test_unavailable_adapter_exposes_persisted_active_and_fails_closed(self):
        self.api.provision(self._document(
            "provision", "engineering-secret-provision", "first",
            tool_key="API_TOKEN", consumer_id="integration:api",
        ), "session")
        environments = UnavailableIntegrationEnvironmentLifecycle(
            "owner", ActiveRepository((
                StoredEnvironment("matching", "secret.api"),
            )),
        )
        api = ProductEngineeringSecretApi(
            "owner", self.repository, self.authentication, clock=lambda: NOW,
            lifecycle=EngineeringSecretLifecycleCoordinator(),
            environments=environments,
        )
        with self.assertRaisesRegex(RuntimeError, "cleanup is unavailable"):
            api.delete(
                self._document("delete", "engineering-secret-delete", ""),
                "session",
            )
        self.assertEqual("active", self.repository.metadata("secret.api")["state"])

    def test_rotate_recovers_matching_pending_materialization_before_commit(self):
        self.api.provision(self._document(
            "provision", "engineering-secret-provision", "first",
            tool_key="API_TOKEN", consumer_id="integration:api",
        ), "session")
        environments = RecordingEnvironments(())
        environments._pending = (
            StoredEnvironment("pending", "secret.api"),
            StoredEnvironment("unrelated", "secret.other"),
        )
        api = ProductEngineeringSecretApi(
            "owner", self.repository, self.authentication, clock=lambda: NOW,
            lifecycle=EngineeringSecretLifecycleCoordinator(),
            environments=environments,
        )
        metadata = api.rotate(
            self._document("rotate", "engineering-secret-rotate", "second"),
            "session",
        )
        self.assertEqual(2, metadata["generation"])
        self.assertEqual(["pending"], environments.cleaned)

    def _document(self, action, purpose, value, *, tool_key="", consumer_id=""):
        digest = engineering_secret_operation_digest(
            action, "secret.api", tool_key, consumer_id, value,
        )
        context = self.authentication.issue(
            "owner", purpose, digest, transport_session_id="session",
        )
        common = {
            "owner_id": "owner", "secret_ref": "secret.api",
            "authentication_context_id": context.context_id, "confirmed": True,
        }
        if action == "provision":
            return common | {
                "tool_key": tool_key, "consumer_id": consumer_id, "value": value,
            }
        if action == "rotate": return common | {"value": value}
        return common


class SecretService:
    def __init__(self, reference):
        self.secret_refs = (reference,)


class SecretPlan:
    def __init__(self, environment_id, reference):
        self.environment_id = environment_id
        self.services = (SecretService(reference),)


class StoredEnvironment:
    def __init__(self, environment_id, reference):
        self.plan = SecretPlan(environment_id, reference)


class RecordingEnvironments:
    def __init__(self, active, fail=False):
        self._active = active
        self._fail = fail
        self.cleaned = []
        self._pending = ()

    def active(self, owner_id):
        if owner_id != "owner":
            raise PermissionError("wrong owner")
        return self._active

    def cleanup(self, owner_id, environment_id):
        if self._fail:
            raise RuntimeError("cleanup failed")
        self.cleaned.append(environment_id)
        return environment_id

    def pending(self, owner_id): return self._pending

    def recover_pending(self, owner_id, environment_id):
        if self._fail:
            raise RuntimeError("pending cleanup failed")
        self.cleaned.append(environment_id)
        return environment_id


class ActiveRepository:
    def __init__(self, active):
        self._active = active

    def active(self):
        return self._active


if __name__ == "__main__":
    unittest.main()
