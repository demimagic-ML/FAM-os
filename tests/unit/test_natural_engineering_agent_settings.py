import unittest

from fam_os.product.natural_engineering_agent import _agent_settings


class NaturalEngineeringAgentSettingsTests(unittest.TestCase):
    def test_qwen_exposes_full_context_as_an_adaptive_ceiling(self):
        settings = _agent_settings(
            "qwen3.8:27b", 64, "Create a directory named reports.",
        )

        self.assertEqual(65_536, settings.context_tokens)
        self.assertEqual("30m", settings.keep_alive)

    def test_small_models_remain_bounded(self):
        settings = _agent_settings(
            "qwen2.5-coder:7b", 64, "Review the entire repository architecture.",
        )

        self.assertEqual(8_192, settings.context_tokens)


if __name__ == "__main__":
    unittest.main()
