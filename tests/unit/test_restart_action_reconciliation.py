import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.composition import CoreStorageComposition
from fam_os.product.restart_recovery import (
    PersistedActionRecord,
    PersistedActionState,
    RestartDisposition,
    StartupActionReconciler,
)
from fam_os.product.request_recovery import (
    RecoverableRequestState,
    RequestRecoveryRecord,
    RequestRestartDisposition,
    RequestWorkKind,
    request_restart_decision,
)
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.action_repository import SqliteActionStateRepository
from fam_os.product.storage.request_recovery_repository import SqliteRequestRecoveryRepository
from tests.contract.schema_application_fixtures import action_proposal, action_result
from tests.contract.schema_core_fixtures import durable_core_values, task_request


class RestartActionReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
        result = SecureStorage(
            database, OwnerKeyStore(root / "master.key", os.geteuid()),
        ).open()
        if result.recovery_required:
            raise RuntimeError(result.reason)
        self.database, self.cipher = result.database, result.cipher
        repositories = CoreStorageComposition(database, self.cipher, "owner").repositories()
        repositories.requests.add(task_request())
        repositories.plans.create(durable_core_values()[1])
        self.actions = SqliteActionStateRepository(database, self.cipher, "owner")

    def tearDown(self) -> None:
        self.database.close()
        self.temporary.cleanup()

    def test_pending_authority_is_discarded_and_uncertain_action_is_verified(self) -> None:
        proposal = action_proposal()
        records = (
            PersistedActionRecord(
                "action-awaiting", "plan-1", "key-awaiting", proposal,
                PersistedActionState.AWAITING_APPROVAL,
            ),
            PersistedActionRecord(
                "action-approved", "plan-1", "key-approved", proposal,
                PersistedActionState.APPROVED, "old-confirmation",
            ),
            PersistedActionRecord(
                "action-invoking", "plan-1", "key-invoking", proposal,
                PersistedActionState.INVOKING, "old-confirmation",
            ),
        )
        for record in records:
            self.assertTrue(self.actions.create(record))
        verifier = _Postconditions(action_result())
        decisions = StartupActionReconciler(self.actions, verifier).reconcile()
        by_id = {item.action_id: item for item in decisions}
        self.assertEqual(
            RestartDisposition.REQUIRE_FRESH_APPROVAL,
            by_id["action-approved"].disposition,
        )
        self.assertFalse(by_id["action-approved"].prior_confirmation_retained)
        approved = self.actions.get("action-approved")
        self.assertEqual(PersistedActionState.AWAITING_APPROVAL, approved.state)
        self.assertIsNone(approved.confirmation_id)
        self.assertEqual(
            PersistedActionState.VERIFIED,
            self.actions.get("action-invoking").state,
        )
        self.assertEqual(1, verifier.calls)
        self.assertTrue(all(not item.provider_retry_allowed for item in decisions))

    def test_inconclusive_postcondition_never_retries_provider(self) -> None:
        record = PersistedActionRecord(
            "action-uncertain", "plan-1", "key-uncertain", action_proposal(),
            PersistedActionState.UNCERTAIN, "old-confirmation",
        )
        self.actions.create(record)
        verifier = _Postconditions(None)
        decision = StartupActionReconciler(self.actions, verifier).reconcile()[0]
        self.assertEqual(RestartDisposition.RECONCILE_POSTCONDITIONS, decision.disposition)
        stored = self.actions.get(record.action_id)
        self.assertEqual(PersistedActionState.RECONCILIATION_REQUIRED, stored.state)
        self.assertIsNone(stored.confirmation_id)
        self.assertFalse(decision.provider_retry_allowed)

    def test_only_read_and_inference_requests_are_safe_to_resume(self) -> None:
        repository = SqliteRequestRecoveryRepository(self.database)
        records = (
            RequestRecoveryRecord(
                "request-1", RequestWorkKind.INFERENCE, RecoverableRequestState.ACTIVE,
            ),
            RequestRecoveryRecord(
                "request-mutation", RequestWorkKind.MUTATION,
                RecoverableRequestState.WAITING_APPROVAL,
            ),
        )
        self.database.execute(
            "INSERT INTO requests VALUES (?,?,?,?,?)",
            ("request-mutation", "ciphertext", "accepted", "now", "now"),
        )
        for record in records:
            repository.put(record)
        decisions = {
            record.request_id: request_restart_decision(record)
            for record in repository.records()
        }
        self.assertEqual(
            RequestRestartDisposition.RESUME_SAFE,
            decisions["request-1"].disposition,
        )
        self.assertEqual(
            RequestRestartDisposition.REQUIRE_FRESH_APPROVAL,
            decisions["request-mutation"].disposition,
        )
        self.assertFalse(any(item.authority_retained for item in decisions.values()))


class _Postconditions:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = 0

    def reconcile(self, _proposal):
        self.calls += 1
        return self.result


if __name__ == "__main__":
    unittest.main()
