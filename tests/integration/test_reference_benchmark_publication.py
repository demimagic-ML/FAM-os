import unittest
from pathlib import Path

from fam_os.product.benchmark_publication import build_publication


class ReferenceBenchmarkPublicationTests(unittest.TestCase):
    def test_publication_keeps_measured_profiles_separate(self) -> None:
        report = build_publication(
            Path("artifacts/scheduler/phase7.5/cpu-only-multi-expert-canonical/baseline-report.json"),
            Path("artifacts/expert_fabric/phase9.3/gemma/verified-parity-20260716-192041-127117.json"),
        )
        self.assertTrue(report.passed)
        self.assertTrue(report.profiles_kept_separate)
        self.assertEqual(report.minimum_hardware.profile_id, "compat-cpu-16gb")
        self.assertEqual(report.full_workstation.profile_id, "full-reference-workstation")
        self.assertIn(("successful_model", "gemma4:26b"),
                      report.full_workstation.measurements)


if __name__ == "__main__":
    unittest.main()
