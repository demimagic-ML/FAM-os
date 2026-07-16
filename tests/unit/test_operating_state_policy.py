import unittest

from fam_os.adaptation.resource_policy import OperatingState, OperatingStatePolicy
from fam_os.experts import ExpertTier


class OperatingStatePolicyTests(unittest.TestCase):
    def test_low_battery_caps_tier_and_disables_speculation(self):
        decision = OperatingStatePolicy().decide(OperatingState(10, False, 50, .1, 0))
        self.assertEqual(ExpertTier.ECONOMICAL, decision.maximum_expert_tier)
        self.assertFalse(decision.speculative_prefetch_allowed)

    def test_thermal_protection_is_stricter_than_battery(self):
        decision = OperatingStatePolicy().decide(OperatingState(10, False, 90, .1, 0))
        self.assertEqual(ExpertTier.MICRO, decision.maximum_expert_tier)
        self.assertIn("thermal.protect", decision.reason_codes)

    def test_foreground_load_disables_prefetch(self):
        decision = OperatingStatePolicy().decide(OperatingState(None, None, 50, .9, 0))
        self.assertFalse(decision.speculative_prefetch_allowed)
        self.assertFalse(decision.background_adaptation_allowed)

    def test_idle_enables_background_only_when_unconstrained(self):
        decision = OperatingStatePolicy().decide(OperatingState(None, None, 50, .1, 600))
        self.assertTrue(decision.background_adaptation_allowed)
        self.assertTrue(decision.speculative_prefetch_allowed)


if __name__ == "__main__":
    unittest.main()
