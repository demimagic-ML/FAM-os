import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]


class MemoryQualityPrivacyEvidenceTests(unittest.TestCase):
    def test_live_encrypted_index_has_quality_and_zero_privacy_leaks(self):
        raw = json.loads((ROOT / "artifacts/memory/phase10.7/memory-quality-privacy.json").read_text())
        self.assertTrue(raw["passed"])
        self.assertEqual(1.0, raw["top1_accuracy"])
        self.assertEqual(0, raw["cross_owner_hit_count"])
        self.assertEqual(0, raw["plaintext_leak_count"])


if __name__ == "__main__":
    unittest.main()
