import unittest

from fam_os.adapters.ollama.context_profile import (
    OllamaContextProfileObserver,
    OllamaContextProfilePolicy,
    parse_ollama_context_profile,
)
from fam_os.adapters.ollama.settings import OllamaSettings
from fam_os.scheduler import ContextMemoryStrategy


def policy(strategy=ContextMemoryStrategy.AUTOREGRESSIVE_KV):
    return OllamaContextProfilePolicy(
        "context.model", "expert.model", "model:q4", strategy, 8_192,
        fixed_runtime_overhead_bytes=100, per_sequence_workspace_bytes=50,
    )


def metadata(**changes):
    values = {
        "general.architecture": "qwen2",
        "qwen2.block_count": 28,
        "qwen2.embedding_length": 3_584,
        "qwen2.attention.head_count": 28,
        "qwen2.attention.head_count_kv": 4,
        "qwen2.context_length": 32_768,
    }
    values.update(changes)
    return {"model_info": values}


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, method, url, payload, timeout_seconds):
        self.calls.append((method, url, payload, timeout_seconds))
        return self.response


class OllamaContextProfileTests(unittest.TestCase):
    def test_derives_qwen_dimensions_and_clamps_to_package_capacity(self):
        profile = parse_ollama_context_profile(metadata(), policy())

        self.assertEqual(profile.maximum_context_tokens, 8_192)
        self.assertEqual(profile.key_value_head_count, 4)
        self.assertEqual(profile.key_dimension, 128)
        self.assertEqual(profile.value_dimension, 128)
        self.assertIn("context_capacity.clamped_to_declared_package", profile.assumption_codes)
        self.assertIn("full_context_cache.no_sliding_window_discount", profile.assumption_codes)

    def test_explicit_laguna_dimensions_do_not_require_attention_head_count_for_derivation(self):
        response = {"model_info": {
            "general.architecture": "laguna", "laguna.block_count": 40,
            "laguna.embedding_length": 2_048, "laguna.attention.head_count": None,
            "laguna.attention.head_count_kv": 8, "laguna.attention.key_length": 128,
            "laguna.attention.value_length": 128, "laguna.context_length": 131_072,
        }}
        profile = parse_ollama_context_profile(response, policy())
        self.assertEqual((profile.key_dimension, profile.value_dimension), (128, 128))
        self.assertIn("attention_heads.fallback_kv_heads", profile.assumption_codes)

    def test_missing_kv_heads_falls_back_conservatively(self):
        profile = parse_ollama_context_profile(
            metadata(**{"qwen2.attention.head_count_kv": None}), policy()
        )
        self.assertEqual(profile.key_value_head_count, 28)
        self.assertIn("kv_heads.fallback_attention_heads", profile.assumption_codes)

    def test_encoder_profile_does_not_claim_persistent_kv_dimensions(self):
        profile = parse_ollama_context_profile(
            metadata(), policy(ContextMemoryStrategy.ENCODER_ACTIVATION_BOUND)
        )
        self.assertIsNone(profile.key_value_head_count)
        self.assertIn("encoder_attention.full_matrix_bound", profile.assumption_codes)

    def test_observer_uses_show_endpoint_and_exact_model_reference(self):
        transport = FakeTransport(metadata())
        observer = OllamaContextProfileObserver(
            OllamaSettings("http://localhost:11434", 10), transport
        )
        observer.observe(policy())
        self.assertEqual(
            transport.calls[0][:3],
            ("POST", "http://localhost:11434/api/show", {"model": "model:q4"}),
        )

    def test_missing_or_invalid_metadata_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "model_info"):
            parse_ollama_context_profile({}, policy())
        with self.assertRaisesRegex(ValueError, "attention.head_count"):
            parse_ollama_context_profile(
                metadata(**{
                    "qwen2.attention.head_count": None,
                    "qwen2.attention.head_count_kv": None,
                }), policy()
            )


if __name__ == "__main__":
    unittest.main()
