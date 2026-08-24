import os
import sys
import tempfile
import unittest
import signal
from pathlib import Path
from unittest.mock import Mock, patch

from fam_os.fabric import PeerEndpoint, PeerServiceConfiguration
from fam_os.product.peer_configuration import PeerConfigurationStore
from fam_os.product.service_cli import run
from fam_os.scheduler import (
    COMPAT_CPU_16GB_PROFILE_ID,
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
)


class ProductServiceCliTests(unittest.TestCase):
    def test_codex_subscription_settings_reach_engineering_composition(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = Mock()
            with patch(
                "fam_os.product.service_cli.LocalProductService",
                return_value=service,
            ) as factory:
                result = run([
                    "--state-root", str(root / "state"),
                    "--runtime-root", str(root / "runtime"),
                    "--external-ollama",
                    "--engineering-provider", "codex-subscription",
                    "--codex-executable", sys.executable,
                    "--codex-model", "gpt-5.6-sol",
                    "--codex-reasoning-effort", "high",
                ])
            self.assertEqual(0, result)
            settings = factory.call_args.args[0].codex_subscription
            self.assertIsNotNone(settings)
            self.assertEqual(Path(sys.executable), settings.executable)
            self.assertEqual("gpt-5.6-sol", settings.model_ref)
            self.assertEqual("high", settings.reasoning_effort)
            self.assertEqual(root / "runtime/codex-inference", settings.work_root)

    def test_restricted_host_profile_reaches_every_product_verifier(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = Mock()
            with (
                patch(
                    "fam_os.product.service_cli.required_sandbox_apparmor_profile",
                    return_value="fam-os-userns",
                ),
                patch(
                    "fam_os.product.service_cli.LocalProductService",
                    return_value=service,
                ) as factory,
            ):
                run([
                    "--state-root", str(root / "state"),
                    "--runtime-root", str(root / "runtime"),
                    "--external-ollama",
                ])

        self.assertEqual(
            "fam-os-userns", factory.call_args.args[0].sandbox_apparmor_profile,
        )

    def test_termination_during_startup_does_not_resume_into_wait(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = Mock()
            handlers = {}

            def register(event, handler):
                handlers[event] = handler

            def interrupt_start():
                handlers[signal.SIGTERM](signal.SIGTERM, None)

            service.start.side_effect = interrupt_start
            with (
                patch(
                    "fam_os.product.service_cli.LocalProductService",
                    return_value=service,
                ),
                patch(
                    "fam_os.product.service_cli.signal.signal",
                    side_effect=register,
                ),
            ):
                result = run([
                    "--state-root", str(root / "state"),
                    "--runtime-root", str(root / "runtime"),
                    "--external-ollama",
                ])

            self.assertEqual(0, result)
            service.start.assert_called_once_with()
            service.wait.assert_not_called()
            service.stop.assert_called_once_with()

    def test_saved_peer_configuration_reaches_composed_service_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            PeerConfigurationStore(
                root / "state/config/peer.json", os.geteuid(),
            ).put(PeerServiceConfiguration(
                True, "Configured server", "0.0.0.0", 48121,
                PeerEndpoint("server.example", 48121),
            ))
            service = Mock()
            with patch("fam_os.product.service_cli.LocalProductService", return_value=service) as factory:
                result = run([
                    "--state-root", str(root / "state"),
                    "--runtime-root", str(root / "runtime"),
                    "--external-ollama",
                ])
            self.assertEqual(0, result)
            settings = factory.call_args.args[0]
            self.assertEqual("Configured server", settings.device_display_name)
            self.assertEqual("0.0.0.0", settings.peer_listen_host)
            self.assertEqual(48121, settings.peer_listen_port)
            service.start.assert_called_once_with()
            service.wait.assert_called_once_with()
            self.assertGreaterEqual(service.stop.call_count, 1)

    def test_explicit_listener_flags_override_saved_bind_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = Mock()
            with patch("fam_os.product.service_cli.LocalProductService", return_value=service) as factory:
                run([
                    "--state-root", str(root / "state"),
                    "--runtime-root", str(root / "runtime"),
                    "--external-ollama", "--device-name", "CLI device",
                    "--peer-listen-host", "127.0.0.1", "--peer-listen-port", "49121",
                ])
            settings = factory.call_args.args[0]
            self.assertEqual("CLI device", settings.device_display_name)
            self.assertEqual("127.0.0.1", settings.peer_listen_host)
            self.assertEqual(49121, settings.peer_listen_port)

    def test_explicit_compat_profile_reaches_managed_service_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = Mock()
            with patch(
                "fam_os.product.service_cli.LocalProductService",
                return_value=service,
            ) as factory:
                run([
                    "--state-root", str(root / "state"),
                    "--runtime-root", str(root / "runtime"),
                    "--validation-profile", COMPAT_CPU_16GB_PROFILE_ID,
                ])

            settings = factory.call_args.args[0]
            self.assertTrue(settings.manage_ollama)
            self.assertEqual(
                COMPAT_CPU_16GB_PROFILE_ID, settings.validation_profile.profile_id,
            )
            self.assertEqual(16 * 1024**3, settings.effective_resource_limits.memory_max_bytes)
            self.assertEqual(0, settings.effective_resource_limits.swap_max_bytes)

    def test_full_profile_can_use_explicit_external_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = Mock()
            with patch(
                "fam_os.product.service_cli.LocalProductService",
                return_value=service,
            ) as factory:
                run([
                    "--state-root", str(root / "state"),
                    "--runtime-root", str(root / "runtime"),
                    "--validation-profile", FULL_REFERENCE_WORKSTATION_PROFILE_ID,
                    "--external-ollama",
                ])

            settings = factory.call_args.args[0]
            self.assertFalse(settings.manage_ollama)
            self.assertIsNone(settings.effective_resource_limits.memory_max_bytes)

    def test_compat_profile_rejects_uncontrolled_external_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(SystemExit) as raised:
                run([
                    "--state-root", str(root / "state"),
                    "--runtime-root", str(root / "runtime"),
                    "--validation-profile", COMPAT_CPU_16GB_PROFILE_ID,
                    "--external-ollama",
                ])
            self.assertEqual(2, raised.exception.code)


if __name__ == "__main__":
    unittest.main()
