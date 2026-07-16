import json
import unittest
from pathlib import Path

from fam_os.experts.phase9_exit import Phase9ExitEvidence

ROOT = Path(__file__).parents[2]


class Phase9ExitGateTests(unittest.TestCase):
    def test_mixed_benchmark_passes_and_majority_stops_early(self):
        raw = json.loads((ROOT / "artifacts/expert_fabric/phase9-exit.json").read_text())
        raw["largest_tier_task_ids"] = tuple(raw["largest_tier_task_ids"])
        raw["phase_artifact_ids"] = tuple(raw["phase_artifact_ids"])
        evidence = Phase9ExitEvidence(**raw)
        self.assertTrue(evidence.passed)
        self.assertEqual(4, evidence.tasks_stopped_before_largest_tier)
        self.assertEqual(5, evidence.total_tasks)
        self.assertEqual(("stable-topological-sort-regression",), evidence.largest_tier_task_ids)


if __name__ == "__main__":
    unittest.main()
