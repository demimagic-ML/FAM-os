import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]


class MemoryRelevanceEvidenceTests(unittest.TestCase):
    def test_every_rejected_candidate_has_exact_reason(self):
        raw = json.loads((ROOT / "artifacts/memory/phase10.4/relevance-gate.json").read_text())
        self.assertEqual(["selected"], raw["selected_record_ids"])
        reasons = {item["record_id"]: item["reason_code"] for item in raw["rejections"]}
        self.assertEqual({
            "overflow": "memory.context-budget", "low": "memory.low-relevance",
            "stale": "memory.stale", "denied": "memory.scope-denied",
        }, reasons)


if __name__ == "__main__":
    unittest.main()
