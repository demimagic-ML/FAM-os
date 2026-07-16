import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fam_os.scheduler import (
    CacheEntryState,
    CachePolicyRequest,
    CacheTelemetryEntry,
    CacheTelemetrySnapshot,
    CacheTier,
    CacheTierPressure,
    DeterministicCacheRetentionPolicy,
)


NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


def entry(name, tier=CacheTier.HOST_PAGE_CACHE, age=0, hits=0, cost=1.0):
    return CacheTelemetryEntry(
        name, tier, CacheEntryState.WARM, 100, 100, hits, 0,
        NOW + timedelta(seconds=age), cost, True, "a" * 64,
    )


def request(entries, required=150, protected=()):
    snapshot = CacheTelemetrySnapshot("snapshot", 1, None, NOW, tuple(entries), True)
    return CachePolicyRequest(
        "request", snapshot,
        (CacheTierPressure(CacheTier.HOST_PAGE_CACHE, required),), protected,
    )


class CachePolicyTests(unittest.TestCase):
    def test_stable_order_prefers_old_low_hit_low_cost_then_identity(self):
        items = (entry("z", hits=2), entry("b"), entry("a"))
        decision = DeterministicCacheRetentionPolicy().decide("decision", request(items))
        self.assertEqual(tuple(item.artifact_id for item in decision.evictions), ("a", "b"))
        self.assertTrue(decision.all_pressures_satisfied)

    def test_protected_active_and_other_tiers_are_never_selected(self):
        active = replace(entry("active"), state=CacheEntryState.ACTIVE, evictable=False)
        items = (entry("protected"), active, entry("gpu", CacheTier.ACCELERATOR_WEIGHTS))
        decision = DeterministicCacheRetentionPolicy().decide(
            "decision", request(items, required=1, protected=("protected",))
        )
        self.assertEqual(decision.evictions, ())
        self.assertFalse(decision.all_pressures_satisfied)

    def test_tiers_are_not_summed_to_satisfy_host_pressure(self):
        items = (entry("host"), entry("gpu", CacheTier.ACCELERATOR_WEIGHTS))
        decision = DeterministicCacheRetentionPolicy().decide(
            "decision", request(items, required=150)
        )
        self.assertEqual(tuple(item.artifact_id for item in decision.evictions), ("host",))
        self.assertFalse(decision.all_pressures_satisfied)

    def test_replay_is_byte_stable_for_same_request_and_decision_id(self):
        value = request((entry("a"), entry("b")))
        policy = DeterministicCacheRetentionPolicy()
        self.assertEqual(policy.decide("decision", value), policy.decide("decision", value))


if __name__ == "__main__":
    unittest.main()
