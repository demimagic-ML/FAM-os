import unittest
from dataclasses import replace

from fam_os.scheduler import (
    ContextMemoryEstimator,
    ContextMemoryModelProfile,
    ContextMemoryReservation,
    ContextMemoryStrategy,
    ContextProfileSource,
)


def autoregressive_profile(**overrides):
    values = {
        "profile_id": "context.qwen",
        "expert_id": "expert.qwen",
        "runtime_artifact_id": "qwen:7b",
        "architecture": "qwen2",
        "strategy": ContextMemoryStrategy.AUTOREGRESSIVE_KV,
        "maximum_context_tokens": 8_192,
        "layer_count": 28,
        "embedding_dimension": 3_584,
        "attention_head_count": 28,
        "key_value_head_count": 4,
        "key_dimension": 128,
        "value_dimension": 128,
        "scalar_bytes": 2,
        "fixed_runtime_overhead_bytes": 100,
        "per_sequence_workspace_bytes": 50,
        "safety_margin_basis_points": 2_500,
        "source": ContextProfileSource.OBSERVED_METADATA,
        "assumption_codes": ("scalar.policy",),
    }
    values.update(overrides)
    return ContextMemoryModelProfile(**values)


class ContextMemoryEstimatorTests(unittest.TestCase):
    def test_autoregressive_estimate_splits_prompt_and_reserved_growth(self):
        profile = autoregressive_profile()
        reservation = ContextMemoryReservation("r1", profile.profile_id, 1_000, 200)
        estimate = ContextMemoryEstimator().estimate("e1", profile, reservation)
        bytes_per_token = 28 * 4 * (128 + 128) * 2

        self.assertEqual(estimate.persistent_context_bytes, 1_000 * bytes_per_token)
        self.assertEqual(estimate.reserved_growth_bytes, 200 * bytes_per_token)
        self.assertEqual(estimate.sequence_workspace_bytes, 50)
        self.assertEqual(estimate.safety_margin_bytes, (estimate.subtotal_bytes + 3) // 4)
        self.assertTrue(estimate.model_resident_bytes_excluded)

    def test_concurrent_sequences_multiply_context_and_workspace(self):
        profile = autoregressive_profile()
        one = ContextMemoryReservation("one", profile.profile_id, 100, 20, 1)
        two = ContextMemoryReservation("two", profile.profile_id, 100, 20, 2)
        estimator = ContextMemoryEstimator()

        first = estimator.estimate("e1", profile, one)
        second = estimator.estimate("e2", profile, two)

        self.assertEqual(second.persistent_context_bytes, 2 * first.persistent_context_bytes)
        self.assertEqual(second.reserved_growth_bytes, 2 * first.reserved_growth_bytes)
        self.assertEqual(second.sequence_workspace_bytes, 2 * first.sequence_workspace_bytes)

    def test_encoder_uses_hidden_state_and_quadratic_attention_bound(self):
        profile = autoregressive_profile(
            strategy=ContextMemoryStrategy.ENCODER_ACTIVATION_BOUND,
            key_value_head_count=None, key_dimension=None, value_dimension=None,
            attention_head_count=12, embedding_dimension=768, layer_count=12,
        )
        reservation = ContextMemoryReservation("r1", profile.profile_id, 512, 0)
        estimate = ContextMemoryEstimator().estimate("e1", profile, reservation)

        self.assertEqual(estimate.persistent_context_bytes, 512 * 768 * 2 * 3)
        self.assertEqual(estimate.attention_workspace_bytes, 12 * 512 * 512 * 2)
        self.assertEqual(estimate.reserved_growth_bytes, 0)

    def test_rejects_capacity_overflow_profile_mismatch_and_encoder_output(self):
        profile = autoregressive_profile(maximum_context_tokens=100)
        estimator = ContextMemoryEstimator()
        with self.assertRaisesRegex(ValueError, "capacity"):
            estimator.estimate(
                "e", profile, ContextMemoryReservation("r", profile.profile_id, 90, 11)
            )
        with self.assertRaisesRegex(ValueError, "another profile"):
            estimator.estimate(
                "e", profile, ContextMemoryReservation("r", "other", 50, 0)
            )
        encoder = replace(
            profile, strategy=ContextMemoryStrategy.ENCODER_ACTIVATION_BOUND,
            key_value_head_count=None, key_dimension=None, value_dimension=None,
        )
        with self.assertRaisesRegex(ValueError, "cannot reserve output"):
            estimator.estimate(
                "e", encoder, ContextMemoryReservation("r", encoder.profile_id, 50, 1)
            )

    def test_strategy_dimensions_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "requires KV"):
            autoregressive_profile(key_value_head_count=None)
        with self.assertRaisesRegex(ValueError, "must not claim"):
            autoregressive_profile(strategy=ContextMemoryStrategy.ENCODER_ACTIVATION_BOUND)


if __name__ == "__main__":
    unittest.main()
