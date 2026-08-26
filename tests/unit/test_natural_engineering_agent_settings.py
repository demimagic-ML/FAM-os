import unittest
import tempfile
from pathlib import Path

from fam_os.product.natural_engineering_agent import (
    _agent_settings, _candidate_toolchain_overlays,
    _postapply_verification_arguments,
)


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

    def test_postapply_verification_reuses_isolated_node_toolchain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = root / "owner"
            candidate = root / "candidate"
            tool = candidate / "app/node_modules/vitest/vitest.mjs"
            owner.mkdir()
            tool.parent.mkdir(parents=True)
            tool.write_text("// vitest\n")

            overlays = _candidate_toolchain_overlays({
                "command": [
                    "node", "app/node_modules/vitest/vitest.mjs",
                    "run", "--root", "app",
                ],
                "timeout_seconds": 60,
            }, owner, candidate)

            self.assertEqual(
                ((candidate / "app/node_modules", owner / "app/node_modules"),),
                overlays,
            )
            replay = _postapply_verification_arguments({
                "command": ["node", "app/node_modules/vitest/vitest.mjs", "run"],
            })
            self.assertEqual("--no-cache", replay["command"][-1])


if __name__ == "__main__":
    unittest.main()
