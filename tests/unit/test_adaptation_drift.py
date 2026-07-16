import unittest

from fam_os.adaptation.drift import AdaptationDriftPolicy, AdaptationSnapshot


def snapshot(identifier, quality=1, latency=1, energy=10):
    return AdaptationSnapshot(identifier, identifier[0] * 64, quality, latency, energy)


class AdaptationDriftTests(unittest.TestCase):
    def test_quality_regression_always_rolls_back(self):
        baseline, candidate = snapshot("a-base"), snapshot("b-new", .99, .5, 5)
        policy = AdaptationDriftPolicy()
        report = policy.evaluate(baseline, candidate)
        self.assertIn("verification.quality-regressed", report.reason_codes)
        receipt = policy.rollback(baseline, candidate, report)
        self.assertEqual("a-base", receipt.restored_snapshot_id)

    def test_latency_and_energy_regression_are_detected(self):
        report = AdaptationDriftPolicy().evaluate(
            snapshot("a-base"), snapshot("b-new", 1, 1.2, 12),
        )
        self.assertEqual(("latency.regressed", "energy.regressed"), report.reason_codes)

    def test_improvement_does_not_roll_back(self):
        policy = AdaptationDriftPolicy()
        report = policy.evaluate(snapshot("a-base"), snapshot("b-new", 1, .8, 8))
        self.assertFalse(report.drifted)
        with self.assertRaises(ValueError):
            policy.rollback(snapshot("a-base"), snapshot("b-new"), report)


if __name__ == "__main__":
    unittest.main()
