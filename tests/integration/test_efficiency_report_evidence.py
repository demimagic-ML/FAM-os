import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]


class EfficiencyEvidenceTests(unittest.TestCase):
    def test_report_contains_raw_meter_samples_and_all_selections(self):
        report = json.loads((
            ROOT / "artifacts/expert_fabric/phase9.7/expert-efficiency-workstation.json"
        ).read_text())
        self.assertEqual("nvidia-smi.power.draw", report["meter_id"])
        self.assertEqual(3, len(report["measurements"]))
        self.assertTrue(all(len(item["power_samples"]) >= 2 for item in report["measurements"]))
        self.assertTrue(all(item["energy_joules"] > 0 for item in report["measurements"]))
        self.assertEqual(
            {"quality_per_byte", "quality_per_second", "quality_per_joule"},
            {item["metric"] for item in report["selections"]},
        )


if __name__ == "__main__":
    unittest.main()
