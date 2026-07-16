import unittest
from datetime import datetime, timedelta, timezone

from fam_os.scheduler.admission_contracts import (
    AdmissionRequest,
    AdmissionStatus,
    EvictionCandidate,
    ResidentWeightEstimate,
    WeightEstimateSource,
)
from fam_os.scheduler.admission_policy import DeterministicAdmissionPolicy
from fam_os.scheduler.live_contracts import ObservationStatus
from fam_os.scheduler.residency_contracts import ExpertResidencyState
from fam_os.schemas import dumps_document, loads_document


NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)
GIB = 1024 ** 3


def candidate(name, state, size, priority, age):
    return EvictionCandidate(name, state, size, priority, NOW - timedelta(hours=age))


def request(available=8 * GIB, state=ExpertResidencyState.COLD, status=ObservationStatus.COMPLETE, authoritative=True):
    return AdmissionRequest(
        "request-1", "observation-2", status, authoritative, available,
        "catalog-1", 7, "expert.requested", state,
        ResidentWeightEstimate(
            "expert.requested", "artifact.requested", 6 * GIB,
            WeightEstimateSource.DECLARED_CONSERVATIVE,
            "expert manifest estimated_resident_bytes; context excluded",
        ),
        "context-estimate-1", 3 * GIB, True,
        (
            candidate("expert.active", ExpertResidencyState.ACTIVE, 9 * GIB, 0, 24),
            candidate("expert.keep", ExpertResidencyState.WARM, 2 * GIB, 20, 48),
            candidate("expert.old", ExpertResidencyState.WARM, 2 * GIB, 10, 72),
            candidate("expert.new", ExpertResidencyState.WARM, 2 * GIB, 10, 2),
        ),
    )


class DeterministicAdmissionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = DeterministicAdmissionPolicy()

    def test_admits_without_eviction_when_increment_fits(self):
        decision = self.policy.decide("decision-1", request(10 * GIB))
        self.assertEqual(decision.status, AdmissionStatus.ADMITTED)
        self.assertEqual(decision.eviction_expert_ids, ())
        self.assertEqual(decision.available_after_bytes, GIB)

    def test_warm_expert_does_not_charge_weights_again(self):
        decision = self.policy.decide(
            "decision-1", request(3 * GIB, ExpertResidencyState.WARM)
        )
        self.assertEqual(decision.status, AdmissionStatus.ADMITTED)
        self.assertEqual(decision.weight_increment_bytes, 0)

    def test_stable_eviction_uses_priority_then_oldest_then_identity(self):
        decision = self.policy.decide("decision-1", request(4 * GIB))
        self.assertEqual(decision.status, AdmissionStatus.ADMITTED)
        self.assertEqual(
            decision.eviction_expert_ids, ("expert.old", "expert.new", "expert.keep")
        )
        self.assertNotIn("expert.active", decision.eviction_expert_ids)

    def test_rejects_when_only_active_memory_could_make_room(self):
        value = request(0)
        decision = self.policy.decide("decision-1", value)
        self.assertEqual(decision.status, AdmissionStatus.REJECTED)
        self.assertEqual(decision.eviction_expert_ids, ("expert.old", "expert.new", "expert.keep"))

    def test_fails_closed_on_degraded_or_non_authoritative_observation(self):
        degraded = self.policy.decide("d1", request(status=ObservationStatus.DEGRADED))
        unknown = self.policy.decide("d2", request(authoritative=False))
        self.assertEqual(degraded.reason_codes[0], "resource_observation.degraded")
        self.assertEqual(unknown.reason_codes[0], "memory_scope.not_authoritative")
        self.assertEqual(degraded.eviction_expert_ids, ())

    def test_request_and_decision_round_trip_as_strict_documents(self):
        value = request()
        self.assertEqual(loads_document(dumps_document(value)), value)
        decision = self.policy.decide("decision-1", value)
        self.assertEqual(loads_document(dumps_document(decision)), decision)

    def test_replay_is_byte_stable(self):
        value = request(4 * GIB)
        first = dumps_document(self.policy.decide("decision-1", value))
        second = dumps_document(self.policy.decide("decision-1", value))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
