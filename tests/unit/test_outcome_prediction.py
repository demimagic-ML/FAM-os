import unittest
from datetime import UTC, datetime

from fam_os.adaptation import LocalOutcomePredictor, VerifiedOutcomeObservation

NOW = datetime(2026, 7, 16, tzinfo=UTC)


def observation(identifier, context, escalation):
    return VerifiedOutcomeObservation(
        identifier, "code-repair", NOW, True, context, escalation, identifier[0] * 64,
    )


class OutcomePredictionTests(unittest.TestCase):
    def test_context_is_conservative_and_escalation_is_observed_rate(self):
        prediction = LocalOutcomePredictor().predict("p", "code-repair", (
            observation("a1", 2048, True), observation("b2", 4096, True),
            observation("c3", 3072, False), observation("d4", 4096, True),
        ))
        self.assertEqual(4096, prediction.predicted_context_tokens)
        self.assertEqual(.75, prediction.escalation_probability)
        self.assertTrue(prediction.prewarm_escalation)

    def test_unverified_outcome_cannot_become_label(self):
        with self.assertRaisesRegex(ValueError, "independently verified"):
            VerifiedOutcomeObservation("bad", "flow", NOW, False, 100, False, "a" * 64)

    def test_small_sample_produces_no_prediction(self):
        self.assertIsNone(LocalOutcomePredictor().predict(
            "p", "code-repair", (observation("a1", 100, False),),
        ))


if __name__ == "__main__":
    unittest.main()
