import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools.phase23_lifecycle.commands import clean_environment, installed_cli
from tools.phase23_lifecycle.contracts import LifecycleSettings
from tools.phase23_lifecycle.scenario import _event, run_lifecycle


class Phase23LifecycleTests(unittest.TestCase):
    def test_settings_require_clean_output_safe_identity_and_loopback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            repository.mkdir()
            settings = LifecycleSettings(
                repository, root / "output", "phase23-lifecycle-01",
            )
            self.assertEqual("phase23-lifecycle-01", settings.run_id)
            with self.assertRaisesRegex(ValueError, "identity"):
                LifecycleSettings(repository, root / "other", "unsafe/id")
            with self.assertRaisesRegex(ValueError, "loopback"):
                LifecycleSettings(
                    repository, root / "other", "safe-id",
                    owner_ollama_url="http://example.test:11434",
                )

    def test_clean_profile_environment_removes_import_overrides(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {
                "PYTHONPATH": "checkout/src", "PYTHONHOME": "/tmp/python",
            }, clear=False):
                environment = clean_environment(Path(temporary))
        self.assertNotIn("PYTHONPATH", environment)
        self.assertNotIn("PYTHONHOME", environment)
        self.assertEqual(temporary, environment["HOME"])

    def test_runner_uses_short_private_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = Mock()
            settings.output_root = Path(temporary) / "output"
            with patch(
                "tools.phase23_lifecycle.scenario.tempfile.mkdtemp",
                side_effect=RuntimeError("captured"),
            ) as mkdtemp:
                with self.assertRaisesRegex(RuntimeError, "captured"):
                    run_lifecycle(settings)
            self.assertEqual("f23l-", mkdtemp.call_args.kwargs["prefix"])

    def test_installed_probe_can_retain_a_structured_unhealthy_receipt(self):
        completed = Mock(
            returncode=1, stdout='{"healthy": false, "reason": "missing_profile"}\n',
            stderr="",
        )
        with patch(
            "tools.phase23_lifecycle.commands.subprocess.run",
            return_value=completed,
        ):
            receipt = installed_cli(
                Path("/installation"), ("host-security", "diagnose"),
                {"HOME": "/tmp"}, accepted_codes=(0, 1),
            )
        self.assertFalse(receipt["healthy"])
        self.assertEqual("missing_profile", receipt["reason"])

    def test_independent_failed_probe_can_be_retained_without_aborting(self):
        events = []
        _event(events, "candidate-sandbox", {"healthy": False}, fatal=False)
        self.assertEqual("candidate-sandbox", events[0]["kind"])
        self.assertFalse(events[0]["passed"])


if __name__ == "__main__":
    unittest.main()
