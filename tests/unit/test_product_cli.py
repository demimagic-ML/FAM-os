import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fam_os.product.cli import main
from fam_os.product.removal import CompleteRemovalReceipt
from fam_os.product.host_security import SandboxHostSecurityReceipt
from fam_os.product.vscode_installation import VsCodeConnectorReceipt


class ProductCliTests(unittest.TestCase):
    def test_host_security_diagnosis_uses_installed_product_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            installation = Mock()
            installation.diagnose.return_value = SimpleNamespace(healthy=True)
            sandbox = SandboxHostSecurityReceipt(
                healthy=True, apparmor_profile="fam-os-userns",
                status="completed", isolation="bubblewrap", reason="",
                implementation_path=f"{temporary}/active/python/host_security.py",
            )
            output = io.StringIO()
            with (
                patch(
                    "fam_os.product.cli.SignedBundleInstallation",
                    return_value=installation,
                ),
                patch(
                    "fam_os.product.cli.diagnose_verifier_sandbox",
                    return_value=sandbox,
                ),
                redirect_stdout(output),
            ):
                result = main([
                    "--prefix", temporary, "host-security", "diagnose",
                ])

        self.assertEqual(0, result)
        self.assertTrue(json.loads(output.getvalue())["healthy"])

    def test_remove_requires_confirmation_and_delegates_complete_owned_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installation = Mock()
            removal = Mock()
            removal.remove.return_value = CompleteRemovalReceipt(
                prefix=str(root / "prefix"), state_root=str(root / "state"),
                runtime_root=str(root / "runtime"),
                extension_root=str(root / "extensions"),
                installation_removed=True, state_removed=True,
                runtime_removed=True, connector_removed=True,
                stopped_units=("fam-os.service", "fam-ollama.service"),
            )
            output = io.StringIO()
            with (
                patch(
                    "fam_os.product.cli.SignedBundleInstallation",
                    return_value=installation,
                ),
                patch("fam_os.product.cli.VsCodeConnectorInstallation"),
                patch(
                    "fam_os.product.cli.CompleteProductRemoval",
                    return_value=removal,
                ) as coordinator,
                redirect_stdout(output),
            ):
                result = main([
                    "--prefix", str(root / "prefix"), "remove",
                    "--state-root", str(root / "state"),
                    "--runtime-root", str(root / "runtime"),
                    "--extension-root", str(root / "extensions"),
                    "--confirm",
                ])

        self.assertEqual(0, result)
        removal.remove.assert_called_once_with(confirmed=True)
        self.assertTrue(json.loads(output.getvalue())["installation_removed"])
        self.assertEqual((root / "state").absolute(), coordinator.call_args.args[2])

    def test_console_requires_healthy_install_and_delegates_without_token_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            installation = Mock()
            installation.diagnose.return_value = SimpleNamespace(healthy=True)
            with (
                patch(
                    "fam_os.product.cli.SignedBundleInstallation",
                    return_value=installation,
                ),
                patch(
                    "fam_os.product.cli.run_console_command", return_value=0,
                ) as console,
            ):
                result = main([
                    "--prefix", temporary, "console",
                    "--runtime-root", temporary, "--port", "9123",
                ])

        self.assertEqual(0, result)
        installation.diagnose.assert_called_once_with()
        console.assert_called_once_with(Path(temporary), 9123)

    def test_console_default_runtime_root_follows_installation_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix = root / "fam-os-current"
            installation = Mock()
            installation.diagnose.return_value = SimpleNamespace(healthy=True)
            with (
                patch.dict("os.environ", {"XDG_RUNTIME_DIR": str(root / "run")}),
                patch(
                    "fam_os.product.cli.SignedBundleInstallation",
                    return_value=installation,
                ),
                patch(
                    "fam_os.product.cli.run_console_command", return_value=0,
                ) as console,
            ):
                result = main([
                    "--prefix", str(prefix), "console",
                ])

        self.assertEqual(0, result)
        console.assert_called_once_with(root / "run/fam-os-current", 8765)

    def test_peer_command_requires_healthy_signed_install_then_delegates(self):
        with tempfile.TemporaryDirectory() as temporary:
            installation = Mock()
            installation.diagnose.return_value = SimpleNamespace(healthy=True)
            with (
                patch("fam_os.product.cli.SignedBundleInstallation", return_value=installation),
                patch("fam_os.product.cli.run_peer_command", return_value=0) as peer,
            ):
                result = main([
                    "--prefix", temporary, "peer", "--state-root", temporary,
                    "identity",
                ])
        self.assertEqual(0, result)
        installation.diagnose.assert_called_once_with()
        peer.assert_called_once()

    def test_exact_vscode_connector_command_hierarchy(self):
        with tempfile.TemporaryDirectory() as temporary:
            installation = Mock()
            installation.diagnose.return_value = SimpleNamespace(healthy=True)
            manager = Mock()
            manager.status.return_value = VsCodeConnectorReceipt(
                True, "fam-os.fam-os-vscode-connector", "0.1.0",
                f"{temporary}/extensions/fam-os.fam-os-vscode-connector-0.1.0",
                "a" * 64,
            )
            output = io.StringIO()
            with (
                patch("fam_os.product.cli.SignedBundleInstallation", return_value=installation),
                patch("fam_os.product.cli.VsCodeConnectorInstallation", return_value=manager),
                redirect_stdout(output),
            ):
                result = main([
                    "--prefix", temporary, "connector", "status", "vscode",
                    "--extension-root", f"{temporary}/extensions",
                ])
        self.assertEqual(result, 0)
        manager.status.assert_called_once_with()
        self.assertTrue(json.loads(output.getvalue())["installed"])

    def test_mcp_serve_uses_running_private_ingress_endpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "active").mkdir()
            bridge = Mock(return_value="stdio-session")
            runner = Mock()
            with (
                patch("fam_os.product.cli.run_mcp_ingress_stdio", bridge),
                patch("fam_os.product.cli.asyncio.run", runner),
            ):
                result = main([
                    "--prefix", str(root), "mcp", "serve",
                    "--client-id", "editor-client",
                    "--runtime-root", str(root / "runtime"),
                ])
        self.assertEqual(0, result)
        bridge.assert_called_once_with(
            (root / "runtime/mcp-ingress.sock").absolute(), "editor-client",
        )
        runner.assert_called_once_with("stdio-session")


if __name__ == "__main__":
    unittest.main()
