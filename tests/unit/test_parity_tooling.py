import json
import tempfile
import unittest
from pathlib import Path

from tools.parity.checks import policy_comparison_checks
from tools.parity.historical_config import load_activation_fixture
from tools.parity.static_policy import StaticExpertCatalog

from tests.unit.execution_fakes import expert
from fam_os.experts import ExpertTier


class HistoricalFixtureTests(unittest.TestCase):
    def test_loads_activation_fixture_as_typed_data(self) -> None:
        payload = {
            "ollama_url": "http://127.0.0.1:11435",
            "policy": "test-policy",
            "kernel_model": "router",
            "expert_model": "expert",
            "evict_kernel_before_expert": True,
            "context_length": 2048,
            "expert_num_predict": 384,
            "timeout_seconds": 600,
            "keep_alive": "5m",
            "prompt": "build it",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            fixture = load_activation_fixture(path)
        self.assertEqual(fixture.policy_name, "test-policy")
        self.assertTrue(fixture.evict_kernel)
        self.assertEqual(fixture.context_tokens, 2048)

    def test_rejects_duplicate_static_experts(self) -> None:
        item = expert("same", "model", ExpertTier.MICRO)
        with self.assertRaisesRegex(ValueError, "unique"):
            StaticExpertCatalog((item, item))


class ParityCheckTests(unittest.TestCase):
    def test_policy_checks_capture_expected_relative_behavior(self) -> None:
        def report(peak: int, rate: float) -> dict:
            return {
                "resources": {"memory_peak_bytes": peak},
                "expert_metrics": {"generation_tokens_per_second": rate},
            }

        checks = policy_comparison_checks(
            {
                "persistent-kernel-14b-expert": report(14_000, 5.0),
                "evict-kernel-14b-expert": report(11_000, 5.0),
                "persistent-kernel-7b-expert": report(7_000, 9.0),
            }
        )
        self.assertTrue(all(check.passed for check in checks))


if __name__ == "__main__":
    unittest.main()
