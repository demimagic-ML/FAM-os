import unittest
from datetime import UTC, datetime, timedelta

from fam_os.memory.access import MemoryAccessContext
from fam_os.memory.manifest import MemoryScope
from fam_os.memory.relevance import MemoryRelevancePolicy, MemoryRetrievalCandidate

NOW = datetime(2026, 7, 16, tzinfo=UTC)
SCOPE = MemoryScope("owner", ("assist",), workspace_ids=("workspace",))
CONTEXT = MemoryAccessContext("owner", "assist", workspace_id="workspace")


def candidate(record, score, tokens, scope=SCOPE, age=timedelta(0)):
    return MemoryRetrievalCandidate(record, scope, NOW - age, score, tokens)


class MemoryRelevanceTests(unittest.TestCase):
    def test_scope_freshness_score_and_volume_all_gate_context(self):
        policy = MemoryRelevancePolicy(.6, timedelta(days=7), 100)
        decision = policy.decide((
            candidate("best", .9, 60), candidate("overflow", .8, 50),
            candidate("low", .2, 10), candidate("stale", .8, 10, age=timedelta(days=8)),
            candidate("other", .95, 10, MemoryScope("other", ("assist",))),
        ), CONTEXT, NOW)
        self.assertEqual(("best",), decision.selected_record_ids)
        reasons = {item.record_id: item.reason_code for item in decision.rejections}
        self.assertEqual("memory.context-budget", reasons["overflow"])
        self.assertEqual("memory.low-relevance", reasons["low"])
        self.assertEqual("memory.stale", reasons["stale"])
        self.assertEqual("memory.scope-denied", reasons["other"])

    def test_selection_is_stable_by_score_then_record_id(self):
        decision = MemoryRelevancePolicy(0, timedelta(days=1), 20).decide(
            (candidate("b", .8, 10), candidate("a", .8, 10)), CONTEXT, NOW,
        )
        self.assertEqual(("a", "b"), decision.selected_record_ids)


if __name__ == "__main__":
    unittest.main()
