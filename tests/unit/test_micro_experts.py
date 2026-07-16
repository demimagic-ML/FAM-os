import json
import unittest
from pathlib import Path

from fam_os.experts import (
    ComplexityMicroExpert, LanguageDetectionMicroExpert,
    RoutingMicroExpert, SafetyMicroExpert,
)


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/micro_experts/classification-v1.json"


class MicroExpertTests(unittest.TestCase):
    def test_every_fixture_is_classified_and_advice_has_no_authority(self):
        cases = json.loads(FIXTURE.read_text())
        experts = {
            "routing": RoutingMicroExpert(), "language": LanguageDetectionMicroExpert(),
            "safety": SafetyMicroExpert(), "complexity": ComplexityMicroExpert(),
        }
        for group, rows in cases.items():
            for text, expected in rows:
                with self.subTest(group=group, text=text):
                    advice = experts[group].advise(text)
                    self.assertEqual(expected, advice.label)
                    self.assertTrue(advice.advisory_only)
                    self.assertGreater(advice.confidence_millionths, 0)

    def test_safety_is_conservative_advice_not_permission(self):
        advice = SafetyMicroExpert().advise("sudo rm -rf data")
        self.assertEqual("review_required", advice.label)
        self.assertEqual(("destructive.delete", "privilege.escalation"), tuple(sorted(advice.reason_codes)))


if __name__ == "__main__":
    unittest.main()
