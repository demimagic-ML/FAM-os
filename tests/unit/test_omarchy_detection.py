import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.omarchy.agent_discovery import InferenceEndpoint
from fam_os.adapters.omarchy.agent_discovery import (
    discover_agents, discover_inference_endpoints,
)
from fam_os.adapters.omarchy.detection import OmarchyDetector


class _Connection:
    def close(self):
        return None


class Runner:
    def run(self, command, timeout_seconds=10):
        return "edge" if command == ("omarchy-version-channel",) else None


class OmarchyDetectionTests(unittest.TestCase):
    def test_agent_capabilities_report_codex_authentication(self):
        agents = discover_agents(
            lambda name: "/usr/bin/codex" if name == "codex" else None,
            "codex", lambda _name, _executable: "authenticated",
        )
        codex = next(item for item in agents if item.agent_id == "codex")
        self.assertTrue(codex.available)
        self.assertTrue(codex.selected)
        self.assertEqual("authenticated", codex.authentication)

    def test_inference_capabilities_include_installed_models(self):
        endpoints = discover_inference_endpoints(
            (("ollama", "http://127.0.0.1:11434", "ollama"),),
            connect=lambda *_args, **_kwargs: _Connection(),
            fetch_json=lambda url: {
                "models": [{"name": "qwen3.8:27b"}],
            } if url.endswith("/api/tags") else {},
        )
        self.assertEqual(("qwen3.8:27b",), endpoints[0].models)

    def test_detects_omarchy_hyprland_capabilities_without_hard_coded_home(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "owner"
            omarchy = root / "share/omarchy"
            omarchy.mkdir(parents=True)
            (omarchy / "version").write_text("4.0.0\n")
            release = root / "os-release"
            release.write_text('ID=arch\nID_LIKE="arch"\n')
            commands = {
                "omarchy": "/usr/bin/omarchy",
                "omarchy-shell": "/usr/bin/omarchy-shell",
                "omarchy-plugin-add": "/usr/bin/omarchy-plugin-add",
                "omarchy-snapshot": "/usr/bin/omarchy-snapshot",
                "uwsm-app": "/usr/bin/uwsm-app",
                "quickshell": "/usr/bin/quickshell",
                "chromium": "/usr/bin/chromium",
                "codex": str(home / ".local/bin/codex"),
                "omarchy-capture-screenshot": "/usr/bin/omarchy-capture-screenshot",
                "wtype": "/usr/bin/wtype",
            }
            detector = OmarchyDetector(
                environment={
                    "HOME": str(home), "OMARCHY_PATH": str(omarchy),
                    "XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "Hyprland",
                    "WAYLAND_DISPLAY": "wayland-1", "HYPRLAND_INSTANCE_SIGNATURE": "instance",
                },
                os_release=release, runner=Runner(), which=commands.get,
                architecture=lambda: "x86_64",
                endpoint_discovery=lambda: (
                    InferenceEndpoint("ollama", "http://127.0.0.1:11434", True, "ollama"),
                ),
            )
            result = detector.detect()
            self.assertTrue(result.host.omarchy)
            self.assertEqual(result.host.version, "4.0.0")
            self.assertEqual(result.host.channel, "edge")
            self.assertEqual(result.host.architecture, "x86_64")
            self.assertEqual(result.host.support_level, "supported")
            self.assertTrue(result.host.supported)
            self.assertEqual(result.desktop.compositor, "hyprland")
            self.assertEqual(result.desktop.manager, "uwsm")
            self.assertTrue(result.features.window_observation)
            self.assertTrue(result.features.quickshell_plugins)
            self.assertTrue(result.features.system_snapshots)
            self.assertEqual(result.paths.home, home)
            self.assertEqual(result.paths.plugin_root, home / ".config/omarchy/plugins")
            self.assertTrue(next(item for item in result.agents if item.agent_id == "codex").available)

    def test_generic_arch_degrades_features_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = root / "os-release"
            release.write_text("ID=arch\n")
            detector = OmarchyDetector(
                environment={"HOME": str(root), "XDG_SESSION_TYPE": "tty"},
                os_release=release, runner=Runner(), which=lambda _name: None,
                endpoint_discovery=lambda: (), architecture=lambda: "aarch64",
            )
            result = detector.detect()
            self.assertFalse(result.host.omarchy)
            self.assertEqual(result.host.support_level, "not-omarchy")
            self.assertEqual(result.host.architecture, "aarch64")
            self.assertFalse(result.desktop.graphical)
            self.assertFalse(result.features.window_observation)
            self.assertFalse(result.features.browser_testing)
            self.assertIn("host.omarchy.not_detected", result.issues)

    def test_x11_keeps_window_observation_without_wayland_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = root / "os-release"
            release.write_text("ID=arch\n")
            detector = OmarchyDetector(
                environment={
                    "HOME": str(root), "XDG_SESSION_TYPE": "x11",
                    "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "i3",
                },
                os_release=release, runner=Runner(), which=lambda _name: None,
                endpoint_discovery=lambda: (), architecture=lambda: "x86_64",
            )
            result = detector.detect()
            self.assertTrue(result.desktop.graphical)
            self.assertTrue(result.features.window_observation)
            self.assertIsNone(result.desktop.compositor)

    def test_generic_wayland_reports_independent_compositor_degradation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = root / "os-release"
            release.write_text("ID=arch\n")
            detector = OmarchyDetector(
                environment={
                    "HOME": str(root), "XDG_SESSION_TYPE": "wayland",
                    "WAYLAND_DISPLAY": "wayland-0", "XDG_CURRENT_DESKTOP": "sway",
                },
                os_release=release, runner=Runner(), which=lambda _name: None,
                endpoint_discovery=lambda: (), architecture=lambda: "aarch64",
            )
            result = detector.detect()
            self.assertTrue(result.desktop.graphical)
            self.assertFalse(result.features.window_observation)
            self.assertIn("desktop.wayland.generic", result.issues)

    def test_omarchy_three_is_detected_but_explicitly_unsupported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            omarchy = root / "omarchy"
            omarchy.mkdir()
            (omarchy / "version").write_text("3.9.2\n")
            release = root / "os-release"
            release.write_text("ID=arch\n")
            result = OmarchyDetector(
                environment={"HOME": str(root), "OMARCHY_PATH": str(omarchy)},
                os_release=release, runner=Runner(),
                which=lambda name: "/usr/bin/omarchy" if name == "omarchy" else None,
                endpoint_discovery=lambda: (), architecture=lambda: "x86_64",
            ).detect()
            self.assertTrue(result.host.omarchy)
            self.assertFalse(result.host.supported)
            self.assertEqual("unsupported", result.host.support_level)

    def test_omarchy_four_aarch64_is_experimental_not_official(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            omarchy = root / "omarchy"
            omarchy.mkdir()
            (omarchy / "version").write_text("4.1.0\n")
            release = root / "os-release"
            release.write_text("ID=arch\n")
            result = OmarchyDetector(
                environment={"HOME": str(root), "OMARCHY_PATH": str(omarchy)},
                os_release=release, runner=Runner(),
                which=lambda name: "/usr/bin/omarchy" if name == "omarchy" else None,
                endpoint_discovery=lambda: (), architecture=lambda: "aarch64",
            ).detect()
            self.assertEqual("experimental", result.host.support_level)
            self.assertFalse(result.host.supported)


if __name__ == "__main__":
    unittest.main()
