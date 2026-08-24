import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from fam_os.core.lifecycle.attempt_contracts import AttemptBudgetPolicy
from fam_os.core.lifecycle.control_contracts import PlanDeadlinePolicy
from fam_os.core.lifecycle.attempt_contracts import AttemptKind
from fam_os.core.lifecycle.global_budget import AttemptBudgetReservation, GlobalAttemptBudget
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.admission_repositories import (
    SqliteRequestAuthorityRegistry,
    SqliteRequestReplayRegistry,
)
from fam_os.product.storage.lifecycle_repositories import (
    SqliteAttemptPolicyRegistry,
    SqliteAttemptReplayRegistry,
    SqliteDeadlinePolicyRegistry,
    SqliteReplayRegistry,
)
from fam_os.product.storage.budget_repository import SqliteGlobalAttemptBudgetLedger
from fam_os.product.storage.final_evidence_repository import SqliteFinalEvidenceRegistry
from fam_os.product.storage.plan_repository import SqlitePlanStateRepository
from fam_os.product.storage.request_repository import SqliteTaskRequestRepository
from fam_os.product.composition import CoreStorageComposition
from tests.contract.schema_core_fixtures import (
    NOW, degradation, durable_core_values, task_request,
)


class DurableCoreRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.result = _open(self.root)

    def tearDown(self) -> None:
        if self.result.database is not None:
            self.result.database.close()
        self.temporary.cleanup()

    def test_replay_reservations_survive_restart_and_batch_is_atomic(self) -> None:
        request = SqliteRequestReplayRegistry(self.result.database)
        attempts = SqliteAttemptReplayRegistry(self.result.database)
        self.assertTrue(request.reserve("request-1"))
        self.assertFalse(request.reserve("request-1"))
        self.assertTrue(attempts.reserve(("attempt-1", "attempt-2")))
        self.assertFalse(attempts.reserve(("attempt-2", "attempt-3")))
        self.assertTrue(SqliteReplayRegistry(self.result.database, "control").reserve("control-1"))
        self.result.database.close()
        self.result = _open(self.root)
        self.assertFalse(SqliteRequestReplayRegistry(self.result.database).reserve("request-1"))

    def test_authority_plan_and_policies_round_trip_encrypted(self) -> None:
        authority = durable_core_values()[0]
        snapshot = durable_core_values()[1]
        authorities = SqliteRequestAuthorityRegistry(
            self.result.database, self.result.cipher, "owner",
        )
        plans = SqlitePlanStateRepository(self.result.database, self.result.cipher, "owner")
        requests = SqliteTaskRequestRepository(
            self.result.database, self.result.cipher, "owner",
        )
        self.assertTrue(requests.add(task_request()))
        self.assertEqual(task_request(), requests.get("request-1"))
        self.assertTrue(requests.update_state("request-1", "admitted", "planned"))
        self.assertTrue(authorities.add(authority))
        self.assertEqual(authority, authorities.get(authority.authority_ref))
        self.assertTrue(plans.create(snapshot))
        self.assertEqual(snapshot, plans.get(snapshot.instance_id))

        attempt_policy = AttemptBudgetPolicy(snapshot.plan.plan_id, (), (), 0, 0)
        deadline_policy = PlanDeadlinePolicy(snapshot.plan.plan_id, NOW + timedelta(minutes=5))
        attempts = SqliteAttemptPolicyRegistry(self.result.database, self.result.cipher, "owner")
        deadlines = SqliteDeadlinePolicyRegistry(self.result.database, self.result.cipher, "owner")
        attempts.add(attempt_policy)
        deadlines.add(deadline_policy)
        self.assertEqual(attempt_policy, attempts.get(snapshot.plan.plan_id))
        self.assertEqual(deadline_policy, deadlines.get(snapshot.plan.plan_id))
        raw = (self.root / "fam.sqlite3").read_bytes()
        self.assertNotIn(b"principal-1", raw)
        self.assertNotIn(b"Generate answer", raw)

    def test_final_evidence_survives_restart_and_rejects_duplicates(self) -> None:
        values = durable_core_values()
        candidate, acceptance = values[4], values[5]
        evidence = SqliteFinalEvidenceRegistry(
            self.result.database, self.result.cipher, "owner",
        )
        self.assertTrue(evidence.add_candidate(candidate))
        self.assertTrue(evidence.add_acceptance(acceptance))
        self.assertTrue(evidence.add_degradation(degradation()))
        self.assertFalse(evidence.add_candidate(candidate))
        self.result.database.close()
        self.result = _open(self.root)
        evidence = SqliteFinalEvidenceRegistry(
            self.result.database, self.result.cipher, "owner",
        )
        self.assertEqual(candidate, evidence.candidate(candidate.candidate_id))
        self.assertEqual(acceptance, evidence.acceptance(acceptance.evidence_id))
        self.assertEqual(degradation(), evidence.degradation("degradation-1"))

    def test_global_budget_is_monotonic_and_survives_restart(self) -> None:
        budget = GlobalAttemptBudget("instance-1", 100, 1_000, 1, 1)
        ledger = SqliteGlobalAttemptBudgetLedger(
            self.result.database, self.result.cipher, "owner", budget,
        )
        repair = AttemptBudgetReservation(
            "reservation-1", "instance-1", "attempt-1", AttemptKind.REPAIR, 40, 400,
        )
        self.assertEqual(40, ledger.reserve(repair).consumed_tokens)
        self.assertIsNone(ledger.reserve(repair))
        too_large = AttemptBudgetReservation(
            "reservation-2", "instance-1", "attempt-2", AttemptKind.ESCALATION, 70, 700,
        )
        self.assertIsNone(ledger.reserve(too_large))
        self.result.database.close()
        self.result = _open(self.root)
        reopened = SqliteGlobalAttemptBudgetLedger(
            self.result.database, self.result.cipher, "owner", budget,
        )
        self.assertEqual(("reservation-1",), reopened.snapshot().reservation_ids)
        with self.assertRaisesRegex(ValueError, "cannot change"):
            SqliteGlobalAttemptBudgetLedger(
                self.result.database, self.result.cipher, "owner",
                GlobalAttemptBudget("instance-1", 200, 1_000, 1, 1),
            )

    def test_production_composition_supplies_only_durable_repositories(self) -> None:
        composition = CoreStorageComposition(
            self.result.database, self.result.cipher, "owner",
        )
        repositories = composition.repositories()
        self.assertTrue(repositories.requests.add(task_request()))
        self.assertTrue(repositories.request_replay.reserve("composed-request"))
        self.assertTrue(repositories.confirmation_replay.reserve("confirmation-1"))
        self.assertTrue(repositories.action_execution_replay.reserve("confirmation-1"))
        budget = GlobalAttemptBudget("composed-instance", 10, 100, 1, 0)
        self.assertEqual("composed-instance", composition.budget_ledger(budget).snapshot().plan_instance_id)


def _open(root: Path):
    database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
    result = SecureStorage(database, OwnerKeyStore(root / "master.key", os.geteuid())).open()
    if result.recovery_required:
        raise RuntimeError(result.reason)
    return result


if __name__ == "__main__":
    unittest.main()
