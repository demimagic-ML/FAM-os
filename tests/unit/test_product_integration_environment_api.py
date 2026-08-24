import unittest
from dataclasses import replace
from threading import Event, Thread

from fam_os.core.engineering import IntegrationEnvironmentStatus

from fam_os.product.integration_environment_api import ProductIntegrationEnvironmentApi
from fam_os.product.engineering_secret_lifecycle import (
    EngineeringSecretLifecycleCoordinator,
)
from tests.contract.schema_integration_environment_fixtures import (
    integration_environment_schema_values,
)


class RecordingRepository:
    def __init__(self, stored=None, fail_put=False, pending=()):
        self.stored = stored
        self.fail_put = fail_put
        self.cleanup = None
        self.intent_state = None
        self.permit = None
        self.pending = pending
        self.recovery = None

    def begin_start(self, plan, candidate):
        self.intent_state = "starting"

    def record_permit(self, permit):
        self.permit = permit

    def record_interrupted(self, environment_id):
        self.intent_state = "recovery_required" if self.permit else "prelaunch_failed"
        return self.intent_state

    def record_intent_recovery(self, environment_id, receipt):
        self.intent_state = "recovered"
        self.recovery = (environment_id, receipt)

    def pending_intents(self): return self.pending
    def record_prelaunch_failed(self, environment_id): self.intent_state = "prelaunch_failed"

    def put_started(self, plan, candidate, result):
        if self.fail_put:
            raise RuntimeError("storage failed")
        self.started = (plan, candidate, result)

    def get(self, environment_id):
        return self.stored

    def active(self):
        return () if self.stored is None else (self.stored,)

    def for_task(self, task_id):
        return (
            () if self.stored is None or self.stored.plan.task_id != task_id
            else (self.stored,)
        )

    def record_cleanup(self, environment_id, receipt, *, reconciled):
        self.cleanup = (environment_id, receipt, reconciled)

    def receipts(self, environment_id):
        return (self.stored.latest_receipt,)


class RecordingService:
    def __init__(self, result):
        self.result = result
        self.cleaned = []

    def start(self, *arguments):
        observer = arguments[-1]
        if callable(observer): observer(self.result.permit)
        return self.result

    def cleanup(self, plan, candidate, receipt, permit):
        self.cleaned.append((plan, candidate, receipt, permit))
        return replace(
            receipt, status=IntegrationEnvironmentStatus.CLEANED,
            cleanup_evidence_ids=("removed:test",),
        )


class RecordingAdapter:
    def __init__(self, receipt):
        self.receipt = receipt
        self.calls = []

    def reconcile(self, plan, candidate_root, permit):
        self.calls.append((plan, candidate_root, permit))
        return self.receipt

    def recover(self, plan, candidate_root, permit):
        self.calls.append(("recover", plan, candidate_root, permit))
        return self.receipt


class Stored:
    def __init__(self, plan, candidate, result, receipt, state="active"):
        self.plan = plan
        self.candidate = candidate
        self.start_result = result
        self.latest_receipt = receipt
        self.state = state


class Intent:
    def __init__(self, plan, candidate, permit):
        self.plan = plan
        self.candidate = candidate
        self.permit = permit


class ProductIntegrationEnvironmentApiTests(unittest.TestCase):
    def setUp(self):
        _spec, self.plan, _permit, self.receipt, self.result = (
            integration_environment_schema_values()
        )
        from fam_os.core.engineering import CandidateWorkspace
        self.candidate = CandidateWorkspace(
            self.plan.candidate_id, self.plan.task_id, "baseline-1",
            "/owner", self.plan.candidate_root, self.plan.created_at,
            "copy", "a" * 64, (),
        )

    def api(self, repository):
        service = RecordingService(self.result)
        cleaned = replace(
            self.receipt, receipt_id="reconciled-1",
            status=IntegrationEnvironmentStatus.CLEANED,
            cleanup_evidence_ids=("reconciled:test",),
        )
        adapter = RecordingAdapter(cleaned)
        return ProductIntegrationEnvironmentApi(
            "owner-1", service, adapter, repository,
        ), service, adapter

    def test_start_persists_and_wrong_owner_is_denied(self):
        repository = RecordingRepository()
        api, service, _adapter = self.api(repository)
        result = api.start(
            "owner-1", self.plan, self.candidate, "grant-1", "core",
            "session-1", lambda: False,
        )
        self.assertEqual(self.result, result)
        self.assertEqual(self.result, repository.started[2])
        with self.assertRaises(PermissionError):
            api.active("other-owner")

    def test_task_query_is_owner_scoped(self):
        stored = Stored(
            self.plan, self.candidate, self.result, self.receipt,
        )
        api, _service, _adapter = self.api(RecordingRepository(stored))
        self.assertEqual((stored,), api.for_task("owner-1", self.plan.task_id))
        with self.assertRaises(PermissionError):
            api.for_task("other-owner", self.plan.task_id)

    def test_failed_persistence_compensates_by_cleanup(self):
        api, service, _adapter = self.api(RecordingRepository(fail_put=True))
        with self.assertRaisesRegex(RuntimeError, "storage failed"):
            api.start(
                "owner-1", self.plan, self.candidate, "grant-1", "core",
                "session-1", lambda: False,
            )
        self.assertEqual(1, len(service.cleaned))

    def test_restart_reconciliation_is_recorded_terminally(self):
        stored = Stored(
            self.plan, self.candidate, self.result, self.receipt,
        )
        repository = RecordingRepository(stored)
        api, _service, adapter = self.api(repository)
        outcomes = api.reconcile_active()
        self.assertTrue(outcomes[0].cleaned)
        self.assertEqual(self.plan.candidate_root, str(adapter.calls[0][1]))
        self.assertTrue(repository.cleanup[2])

    def test_terminal_environment_is_rejected_before_adapter_effect(self):
        stored = Stored(
            self.plan, self.candidate, self.result, self.receipt, state="cleaned",
        )
        api, service, adapter = self.api(RecordingRepository(stored))
        with self.assertRaisesRegex(PermissionError, "only an active"):
            api.cleanup("owner-1", self.plan.environment_id)
        with self.assertRaisesRegex(PermissionError, "only an active"):
            api.reconcile("owner-1", self.plan.environment_id)
        self.assertEqual([], service.cleaned)
        self.assertEqual([], adapter.calls)

    def test_secret_drain_cannot_miss_an_in_flight_start(self):
        plan = PlanWithSecret(self.plan.environment_id, "secret.api")
        started = Event(); release = Event(); attempted = Event()
        repository = LiveRepository()
        service = BlockingService(self.result, started, release)
        lifecycle = EngineeringSecretLifecycleCoordinator()
        cleaned = replace(
            self.receipt, status=IntegrationEnvironmentStatus.CLEANED,
            cleanup_evidence_ids=("removed:test",),
        )
        api = ProductIntegrationEnvironmentApi(
            "owner-1", service, RecordingAdapter(cleaned), repository, lifecycle,
        )
        start_thread = Thread(target=lambda: api.start(
            "owner-1", plan, self.candidate, "grant-1", "core", "session-1",
            lambda: False,
        ))
        drain_thread = Thread(target=lambda: (
            attempted.set(),
            lifecycle.drain_reference("secret.api", "owner-1", api),
        ))
        start_thread.start(); self.assertTrue(started.wait(1))
        drain_thread.start(); self.assertTrue(attempted.wait(1))
        self.assertTrue(drain_thread.is_alive())
        self.assertEqual((), repository.active())
        release.set(); start_thread.join(2); drain_thread.join(2)
        self.assertFalse(start_thread.is_alive())
        self.assertFalse(drain_thread.is_alive())
        self.assertEqual("cleaned", repository.stored.state)

    def test_incomplete_intents_close_prelaunch_or_recover_exact_permit(self):
        no_effect = Intent(self.plan, self.candidate, None)
        interrupted = Intent(self.plan, self.candidate, self.result.permit)
        repository = RecordingRepository(pending=(no_effect, interrupted))
        api, _service, adapter = self.api(repository)
        outcomes = api.recover_incomplete()
        self.assertEqual((True, True), tuple(item.cleaned for item in outcomes))
        self.assertEqual("recovered", repository.intent_state)
        self.assertEqual(self.plan.environment_id, repository.recovery[0])
        self.assertEqual("recover", adapter.calls[0][0])
        repository.pending = (interrupted,)
        receipt = api.recover_pending("owner-1", self.plan.environment_id)
        self.assertEqual(IntegrationEnvironmentStatus.CLEANED, receipt.status)


class LiveRepository(RecordingRepository):
    def put_started(self, plan, candidate, result):
        self.stored = Stored(plan, candidate, result, result.receipt)

    def record_cleanup(self, environment_id, receipt, *, reconciled):
        super().record_cleanup(environment_id, receipt, reconciled=reconciled)
        self.stored.state = "cleaned"


class BlockingService(RecordingService):
    def __init__(self, result, started, release):
        super().__init__(result)
        self._started = started
        self._release = release

    def start(self, *arguments):
        self._started.set()
        if not self._release.wait(2):
            raise RuntimeError("test start release timed out")
        return self.result


class PlanWithSecret:
    def __init__(self, environment_id, secret_ref):
        self.environment_id = environment_id
        self.services = (ServiceWithSecret(secret_ref),)


class ServiceWithSecret:
    def __init__(self, secret_ref):
        self.secret_refs = (secret_ref,)


if __name__ == "__main__":
    unittest.main()
