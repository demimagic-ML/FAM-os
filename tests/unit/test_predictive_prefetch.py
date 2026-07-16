import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fam_os.scheduler import (
    ArtifactAccessSequence,
    CacheEntryState,
    CacheTelemetryEntry,
    CacheTelemetrySnapshot,
    CacheTier,
    DeterministicPrefetchAdmissionPolicy,
    DeterministicTransitionPredictor,
    PrefetchAdmissionStatus,
    PrefetchCandidate,
    PrefetchPolicyRequest,
    PrefetchPredictionRequest,
    PrefetchResourceBudget,
)


NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


def prediction_request(history=None):
    candidate = PrefetchCandidate("b", CacheTier.HOST_PAGE_CACHE, 1000, 100, 10.0)
    history = history or (
        ArtifactAccessSequence("s1", NOW, ("a", "b"), "a" * 64),
        ArtifactAccessSequence("s2", NOW, ("a", "b"), "b" * 64),
    )
    return PrefetchPredictionRequest("request", "a", NOW, (candidate,), history, 2, 1.0, 60)


def policy_request():
    prediction = DeterministicTransitionPredictor().predict("prediction", prediction_request())
    entry = CacheTelemetryEntry(
        "b", CacheTier.HOST_PAGE_CACHE, CacheEntryState.COLD, 1000, 0,
        0, 0, None, 10.0, False, "c" * 64,
    )
    snapshot = CacheTelemetrySnapshot("snapshot", 1, None, NOW, (entry,), False)
    budget = PrefetchResourceBudget(100, 100, 100, 1000, 500, 1, 200, 0)
    return PrefetchPolicyRequest("policy-request", prediction, snapshot, budget, NOW, 0, False)


class PredictivePrefetchTests(unittest.TestCase):
    def test_two_identical_transitions_produce_bounded_prediction(self):
        prediction = DeterministicTransitionPredictor().predict("prediction", prediction_request())
        self.assertEqual(prediction.candidate.artifact_id, "b")
        self.assertEqual(prediction.transition_observations, 2)
        self.assertEqual(prediction.confidence, 1.0)

    def test_insufficient_history_produces_no_prediction(self):
        one = (ArtifactAccessSequence("s1", NOW, ("a", "b"), "a" * 64),)
        self.assertIsNone(
            DeterministicTransitionPredictor().predict("prediction", prediction_request(one))
        )

    def test_admission_preserves_every_bound_without_eviction(self):
        decision = DeterministicPrefetchAdmissionPolicy().decide("decision", policy_request())
        self.assertEqual(decision.status, PrefetchAdmissionStatus.ADMITTED)
        self.assertEqual(decision.reserved_prefetch_bytes, 100)
        self.assertEqual(decision.selected_eviction_artifact_ids, ())

    def test_expiry_reserve_concurrency_and_waste_fail_closed(self):
        request = policy_request()
        expired = replace(request, evaluated_at=NOW + timedelta(seconds=61))
        reserve = replace(request, budget=replace(request.budget, host_available_bytes=550))
        concurrent = replace(request, in_flight_prefetches=1)
        waste = replace(request, budget=replace(request.budget, current_waste_bytes=150))
        policy = DeterministicPrefetchAdmissionPolicy()
        reasons = set()
        for item in (expired, reserve, concurrent, waste):
            decision = policy.decide("decision", item)
            self.assertEqual(decision.status, PrefetchAdmissionStatus.REJECTED)
            reasons.update(decision.reasons)
        self.assertEqual(reasons, {
            "prediction.expired", "capacity.operating_system_reserve",
            "budget.concurrent_prefetches_exceeded", "budget.maximum_waste_exceeded",
        })

    def test_already_warm_candidate_is_not_prefetched(self):
        request = policy_request()
        warm = replace(
            request.snapshot.entries[0], state=CacheEntryState.WARM,
            observed_bytes=100, last_accessed_at=NOW, evictable=True,
        )
        changed = replace(request, snapshot=replace(request.snapshot, entries=(warm,)))
        decision = DeterministicPrefetchAdmissionPolicy().decide("decision", changed)
        self.assertIn("cache.candidate_already_resident", decision.reasons)


if __name__ == "__main__":
    unittest.main()
