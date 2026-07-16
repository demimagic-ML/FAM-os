import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]


class ExpertEvolutionEvidenceTests(unittest.TestCase):
    def test_all_changes_are_unapplied_approval_required_proposals(self):
        report = json.loads((
            ROOT / "artifacts/expert_fabric/phase9.8/expert-evolution-report.json"
        ).read_text())
        self.assertEqual({"split", "merge", "retire"}, {item["action"] for item in report["proposals"]})
        self.assertTrue(all(item["approval_required"] for item in report["proposals"]))
        self.assertTrue(all(not item["state_mutated"] for item in report["proposals"]))
        self.assertEqual([], report["applied_proposal_ids"])


if __name__ == "__main__":
    unittest.main()
