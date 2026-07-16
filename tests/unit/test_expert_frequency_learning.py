import unittest
from datetime import UTC, datetime

from fam_os.scheduler.frequency_learning import ExpertUseObservation, LocalExpertFrequencyLearner

NOW = datetime(2026, 7, 16, tzinfo=UTC)


class ExpertFrequencyLearningTests(unittest.TestCase):
    def test_profile_counts_local_verified_usage(self):
        profile = LocalExpertFrequencyLearner().learn("profile", (
            ExpertUseObservation("1", "small", NOW, True),
            ExpertUseObservation("2", "small", NOW, False),
            ExpertUseObservation("3", "large", NOW, True),
        ))
        values = {item.expert_id: item for item in profile.frequencies}
        self.assertEqual(2, values["small"].total_uses)
        self.assertEqual(1, values["small"].verified_uses)
        self.assertAlmostEqual(2 / 3, values["small"].frequency)
        self.assertTrue(profile.local_only)


if __name__ == "__main__":
    unittest.main()
