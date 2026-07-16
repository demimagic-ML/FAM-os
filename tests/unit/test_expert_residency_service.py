import unittest
from datetime import datetime, timedelta, timezone

from fam_os.core.ports.inference import LoadedModel
from fam_os.scheduler import (
    ExpertResidencyIdentity,
    ExpertResidencyService,
    ExpertResidencyState,
    InMemoryExpertResidencyRepository,
    ResidencyEvictionCoordinator,
    ResidencyLease,
    ResidencyTransitionReason,
    initial_cold_residency_catalog,
)
from fam_os.scheduler.residency_ports import (
    ResidencyRevisionConflict,
    ResidencyTransitionError,
)


NOW = datetime(2026, 7, 16, 18, 0, tzinfo=timezone.utc)


class FakeRuntime:
    def __init__(self, *, failure=None, observation_failure=None):
        self.failure = failure
        self.observation_failure = observation_failure
        self.unloaded = []
        self.models = ()

    def unload(self, model_ref):
        self.unloaded.append(model_ref)
        if self.failure:
            raise self.failure

    def loaded_models(self):
        if self.observation_failure:
            raise self.observation_failure
        return self.models


def loaded():
    return LoadedModel("qwen:7b", 6_000, 5_000, 2_048)


def lease(identity="lease-1", request="request-1", offset=0):
    acquired = NOW + timedelta(seconds=offset)
    return ResidencyLease(identity, request, acquired, acquired + timedelta(minutes=5))


class ExpertResidencyServiceTests(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryExpertResidencyRepository()
        self.repository.initialize(initial_cold_residency_catalog(
            "catalog-1", (ExpertResidencyIdentity("expert.qwen", "qwen:7b"),), NOW
        ))
        self.service = ExpertResidencyService(self.repository)

    def warm(self):
        return self.service.reconcile((loaded(),), NOW + timedelta(seconds=1), 0)

    def test_provider_load_moves_cold_to_warm_with_observed_resources(self):
        catalog = self.warm()
        record = catalog.require("expert.qwen")

        self.assertEqual(record.state, ExpertResidencyState.WARM)
        self.assertEqual(record.resident_bytes, 6_000)
        self.assertEqual(record.transition_reason, ResidencyTransitionReason.PROVIDER_LOADED)
        self.assertEqual((catalog.revision, record.record_revision), (1, 1))

    def test_leases_drive_warm_active_active_warm(self):
        warm = self.warm()
        first = self.service.acquire("expert.qwen", lease(offset=2), warm.revision)
        second = self.service.acquire(
            "expert.qwen", lease("lease-2", "request-2", 3), first.revision
        )
        still_active = self.service.release(
            "expert.qwen", "lease-1", NOW + timedelta(seconds=4), second.revision
        )
        final = self.service.release(
            "expert.qwen", "lease-2", NOW + timedelta(seconds=5), still_active.revision
        )

        self.assertEqual(first.require("expert.qwen").state, ExpertResidencyState.ACTIVE)
        self.assertEqual(len(second.require("expert.qwen").active_leases), 2)
        self.assertEqual(still_active.require("expert.qwen").state, ExpertResidencyState.ACTIVE)
        self.assertEqual(final.require("expert.qwen").state, ExpertResidencyState.WARM)

    def test_expired_leases_return_expert_to_warm(self):
        warm = self.warm()
        active = self.service.acquire("expert.qwen", lease(offset=2), warm.revision)
        expired = self.service.expire_leases(NOW + timedelta(minutes=10), active.revision)

        record = expired.require("expert.qwen")
        self.assertEqual(record.state, ExpertResidencyState.WARM)
        self.assertEqual(record.transition_reason, ResidencyTransitionReason.LEASES_EXPIRED)

    def test_evicting_blocks_leases_and_confirmed_unload_becomes_cold(self):
        warm = self.warm()
        started = self.service.begin_eviction(
            "expert.qwen", "evict-1", NOW + timedelta(seconds=2), warm.revision
        )
        with self.assertRaisesRegex(ResidencyTransitionError, "cannot acquire"):
            self.service.acquire("expert.qwen", lease(offset=3), started.revision)
        cold = self.service.confirm_eviction(
            "expert.qwen", "evict-1", NOW + timedelta(seconds=4), started.revision
        )

        self.assertEqual(cold.require("expert.qwen").state, ExpertResidencyState.COLD)
        self.assertIsNone(cold.require("expert.qwen").resident_bytes)

    def test_provider_reconciliation_recovers_crashed_evicting_transition(self):
        warm = self.warm()
        started = self.service.begin_eviction(
            "expert.qwen", "evict-1", NOW + timedelta(seconds=2), warm.revision
        )
        cold = self.service.reconcile((), NOW + timedelta(seconds=3), started.revision)

        self.assertEqual(cold.require("expert.qwen").state, ExpertResidencyState.COLD)
        self.assertEqual(
            cold.require("expert.qwen").transition_reason,
            ResidencyTransitionReason.EVICTION_CONFIRMED,
        )

    def test_active_provider_disappearance_fails_without_mutation(self):
        warm = self.warm()
        active = self.service.acquire("expert.qwen", lease(offset=2), warm.revision)
        with self.assertRaisesRegex(ResidencyTransitionError, "disappeared"):
            self.service.reconcile((), NOW + timedelta(seconds=3), active.revision)
        self.assertEqual(self.repository.read(), active)

    def test_successful_coordinator_confirms_absence_barrier(self):
        warm = self.warm()
        runtime = FakeRuntime()
        coordinator = ResidencyEvictionCoordinator(self.service, runtime)
        cold = coordinator.evict(
            "expert.qwen", "evict-1", NOW + timedelta(seconds=2),
            NOW + timedelta(seconds=3), warm.revision,
        )

        self.assertEqual(runtime.unloaded, ["qwen:7b"])
        self.assertEqual(cold.require("expert.qwen").state, ExpertResidencyState.COLD)

    def test_failed_coordinator_restores_warm_state_and_rethrows(self):
        warm = self.warm()
        coordinator = ResidencyEvictionCoordinator(
            self.service, FakeRuntime(failure=RuntimeError("not absent"))
        )
        coordinator.runtime.models = (loaded(),)
        with self.assertRaisesRegex(RuntimeError, "not absent"):
            coordinator.evict(
                "expert.qwen", "evict-1", NOW + timedelta(seconds=2),
                NOW + timedelta(seconds=3), warm.revision,
            )
        record = self.repository.read().require("expert.qwen")
        self.assertEqual(record.state, ExpertResidencyState.WARM)
        self.assertEqual(record.transition_reason, ResidencyTransitionReason.EVICTION_ABORTED)

    def test_unload_error_with_confirmed_absence_finishes_cold(self):
        warm = self.warm()
        coordinator = ResidencyEvictionCoordinator(
            self.service, FakeRuntime(failure=RuntimeError("late response"))
        )
        cold = coordinator.evict(
            "expert.qwen", "evict-1", NOW + timedelta(seconds=2),
            NOW + timedelta(seconds=3), warm.revision,
        )
        self.assertEqual(cold.require("expert.qwen").state, ExpertResidencyState.COLD)

    def test_unload_and_observation_error_leave_recoverable_evicting_state(self):
        warm = self.warm()
        coordinator = ResidencyEvictionCoordinator(
            self.service,
            FakeRuntime(
                failure=RuntimeError("not confirmed"),
                observation_failure=RuntimeError("provider down"),
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "provider down"):
            coordinator.evict(
                "expert.qwen", "evict-1", NOW + timedelta(seconds=2),
                NOW + timedelta(seconds=3), warm.revision,
            )
        self.assertEqual(
            self.repository.read().require("expert.qwen").state,
            ExpertResidencyState.EVICTING,
        )

    def test_stale_revision_and_illegal_cold_lease_fail(self):
        with self.assertRaisesRegex(ResidencyTransitionError, "cannot acquire"):
            self.service.acquire("expert.qwen", lease(), 0)
        self.warm()
        with self.assertRaisesRegex(ResidencyTransitionError, "stale"):
            self.service.expire_leases(NOW + timedelta(seconds=2), 0)
        replacement = initial_cold_residency_catalog(
            "catalog-1", (ExpertResidencyIdentity("expert.qwen", "qwen:7b"),), NOW
        )
        with self.assertRaises(ResidencyRevisionConflict):
            self.repository.compare_and_swap(0, replacement)


if __name__ == "__main__":
    unittest.main()
