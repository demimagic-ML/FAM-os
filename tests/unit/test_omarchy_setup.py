import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.omarchy.agent_discovery import AgentCapability, InferenceEndpoint
from fam_os.adapters.omarchy.detection import (
    DesktopCapability,
    FeatureCapability,
    HostCapability,
    OmarchyCapabilities,
)
from fam_os.adapters.omarchy.environment import omarchy_paths
from fam_os.product.omarchy_setup import DEFAULT_PLUGIN_URL, OmarchySetup


class _Detector:
    def __init__(self, capabilities):
        self.capabilities = capabilities

    def detect(self):
        return self.capabilities


class _Commands:
    def __init__(self, plugin_root: Path):
        self.plugin_root = plugin_root
        self.calls: list[tuple[str, ...]] = []
        self.enabled = False

    def __call__(self, command, **_kwargs):
        call = tuple(command)
        self.calls.append(call)
        stdout = ""
        target = self.plugin_root / "fam.os"
        if call[:3] == ("omarchy", "plugin", "add"):
            (target / ".git").mkdir(parents=True)
            (target / "manifest.json").write_text(
                json.dumps({"schemaVersion": 1, "id": "fam.os"}),
                encoding="utf-8",
            )
            self.enabled = "--enable" in call
        elif call == ("omarchy", "plugin", "list", "--json"):
            stdout = (
                json.dumps(
                    [
                        {"id": "fam.os", "enabled": self.enabled},
                    ]
                )
                if target.is_dir()
                else "[]"
            )
        elif call == ("omarchy", "plugin", "enable", "fam.os"):
            self.enabled = True
        elif call[:4] == ("omarchy", "plugin", "remove", "fam.os"):
            shutil.rmtree(target, ignore_errors=True)
            self.enabled = False
        elif call[:5] == ("git", "-C", str(target), "remote", "get-url"):
            stdout = DEFAULT_PLUGIN_URL + "\n"
        return subprocess.CompletedProcess(command, 0, stdout, "")


def _integration(root: Path) -> Path:
    integration = root / "integration"
    for relative in ("desktop", "launcher", "usage-collector", "menu", "hooks"):
        (integration / relative).mkdir(parents=True)
    (integration / "desktop/fam-os.desktop").write_text(
        "[Desktop Entry]\nX-FAM-Managed=true\n",
        encoding="utf-8",
    )
    for relative in (
        "launcher/omarchy-fam",
        "usage-collector/omarchy-agent-usage-fam",
    ):
        (integration / relative).write_text(
            "#!/bin/sh\nexit 0\n",
            encoding="utf-8",
        )
    (integration / "menu/omarchy-menu.json").write_text(
        json.dumps(
            {
                "fam": {"label": "FAM"},
                "fam.console": {"label": "Console", "action": "fam console"},
                "fam.goal": {"label": "Goal", "action": "fam goal"},
                "fam.doctor": {"label": "Doctor", "action": "fam-os doctor"},
                "fam.repair": {"label": "Repair", "action": "fam-os repair"},
            }
        )
    )
    (integration / "hooks/fam-os").write_text(
        "#!/bin/bash\n# X-FAM-Managed=true\nexit 0\n",
        encoding="utf-8",
    )
    return integration


def _fixture(root: Path, *, version: str = "4.0.0", architecture: str = "x86_64"):
    home = root / "home"
    paths = omarchy_paths(
        {
            "HOME": str(home),
            "XDG_DATA_HOME": str(home / "data"),
            "XDG_CONFIG_HOME": str(home / "config"),
            "XDG_STATE_HOME": str(home / "state"),
            "XDG_RUNTIME_DIR": str(home / "run"),
            "OMARCHY_PATH": str(root / "omarchy"),
        },
        home=home,
        uid=1000,
    )
    support_level = (
        "supported"
        if version.startswith("4.") and architecture == "x86_64"
        else "experimental"
        if version.startswith("4.") and architecture == "aarch64"
        else "unsupported"
    )
    capabilities = OmarchyCapabilities(
        HostCapability(
            "arch",
            ("arch",),
            version,
            "edge",
            architecture,
            True,
            support_level,
            support_level == "supported",
        ),
        DesktopCapability(
            "wayland",
            ("Hyprland",),
            "hyprland",
            "uwsm",
            "quickshell",
            True,
        ),
        FeatureCapability(True, True, True, True, True, True, True),
        (
            AgentCapability(
                "codex",
                "/usr/bin/codex",
                True,
                "hosted-engineering",
                "authenticated",
                True,
            ),
        ),
        (
            InferenceEndpoint(
                "ollama",
                "http://127.0.0.1:11434",
                True,
                "ollama",
            ),
        ),
        (),
        paths,
        (),
    )
    commands = _Commands(paths.plugin_root)
    setup = OmarchySetup(
        paths=paths,
        integration_root=_integration(root),
        detector=_Detector(capabilities),
        run=commands,
        which=lambda name: f"/usr/bin/{name}",
    )
    return paths, commands, setup


class OmarchySetupTests(unittest.TestCase):
    def test_setup_is_idempotent_and_uses_official_git_plugin_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, commands, setup = _fixture(Path(directory))

            first = setup.setup(start=False)
            environment_path = paths.config_home / "fam-os/service.env"
            environment_path.write_text(
                environment_path.read_text().replace(
                    "FAM_OS_ENGINEERING_PROVIDER=codex-subscription",
                    "FAM_OS_ENGINEERING_PROVIDER=ollama",
                ),
                encoding="utf-8",
            )
            second = setup.setup(start=False)

            self.assertTrue(first.configured)
            self.assertTrue(second.configured)
            self.assertEqual("codex-subscription", first.engineering_provider)
            self.assertEqual("ollama", second.engineering_provider)
            self.assertTrue((paths.plugin_root / "fam.os/.git").is_dir())
            add_calls = [
                call
                for call in commands.calls
                if call[:3] == ("omarchy", "plugin", "add")
            ]
            self.assertEqual(
                [
                    (
                        "omarchy",
                        "plugin",
                        "add",
                        DEFAULT_PLUGIN_URL,
                        "--enable",
                        "--yes",
                    ),
                ],
                add_calls,
            )
            self.assertFalse(
                any(
                    call[:3] == ("omarchy", "plugin", "enable")
                    for call in commands.calls
                )
            )
            manifest = json.loads(setup.manifest_path.read_text())
            self.assertEqual(DEFAULT_PLUGIN_URL, manifest["widget_source"])
            environment = environment_path.read_text()
            self.assertIn("FAM_OS_ENGINEERING_PROVIDER=ollama", environment)
            self.assertIn(
                "FAM_OS_OLLAMA_URL=http://127.0.0.1:11434",
                environment,
            )
            menu = json.loads(
                "\n".join(
                    line
                    for line in (
                        paths.config_home / "omarchy/extensions/omarchy-menu.jsonc"
                    )
                    .read_text()
                    .splitlines()
                    if not line.startswith("//")
                )
            )
            self.assertEqual("FAM", menu["fam"]["label"])
            self.assertIn(
                (
                    "omarchy",
                    "hook",
                    "install",
                    "post-update",
                    str(setup.integration_root / "hooks/fam-os"),
                ),
                commands.calls,
            )

    def test_menu_merge_and_remove_preserve_unrelated_user_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, _commands, setup = _fixture(Path(directory))
            menu = paths.config_home / "omarchy/extensions/omarchy-menu.jsonc"
            menu.parent.mkdir(parents=True)
            menu.write_text(
                "// personal entry\n"
                '{"personal":{/* keep this */"label":"Notes",'
                '"url":"https://example.test/path",}, // inline\n'
                '"fam.custom":{"label":"My FAM shortcut"},\n}\n',
                encoding="utf-8",
            )

            setup.setup(start=False)
            setup.remove()

            value = json.loads(
                "\n".join(
                    line
                    for line in menu.read_text().splitlines()
                    if not line.startswith("//")
                )
            )
            self.assertEqual(
                {
                    "personal": {
                        "label": "Notes",
                        "url": "https://example.test/path",
                    },
                    "fam.custom": {"label": "My FAM shortcut"},
                },
                value,
            )

    def test_repair_updates_and_remove_uses_omarchy_plugin_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, commands, setup = _fixture(Path(directory))
            setup.setup(start=False)

            repaired = setup.repair(widget=True)
            removed = setup.remove()

            self.assertTrue(repaired.widget_installed)
            self.assertFalse(removed.widget_installed)
            self.assertIn(
                ("omarchy", "plugin", "update", "fam.os", "--yes"),
                commands.calls,
            )
            self.assertIn(
                ("omarchy", "plugin", "remove", "fam.os", "--yes"),
                commands.calls,
            )
            self.assertFalse((paths.plugin_root / "fam.os").exists())

    def test_repair_reenables_plugin_without_touching_omarchy_bar_placement(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, commands, setup = _fixture(Path(directory))
            setup.setup(start=False)
            commands.enabled = False
            placement = paths.config_home / "omarchy/current/theme/bar-placement.json"
            placement.parent.mkdir(parents=True)
            expected = '{"right":["clock","fam.os"]}\n'
            placement.write_text(expected, encoding="utf-8")

            repaired = setup.repair(widget=True)

            self.assertTrue(repaired.widget_enabled)
            self.assertIn(
                ("omarchy", "plugin", "enable", "fam.os"),
                commands.calls,
            )
            self.assertEqual(expected, placement.read_text(encoding="utf-8"))

    def test_setup_refuses_an_unowned_plugin_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, _commands, setup = _fixture(Path(directory))
            (paths.plugin_root / "fam.os").mkdir(parents=True)

            with self.assertRaisesRegex(RuntimeError, "not the configured Git-backed"):
                setup.setup(start=False)

    def test_omarchy_three_is_rejected_and_arm_requires_explicit_experimental(self):
        with tempfile.TemporaryDirectory() as directory:
            _paths, _commands, old_setup = _fixture(
                Path(directory) / "old",
                version="3.9.9",
            )
            with self.assertRaisesRegex(RuntimeError, "supports Omarchy 4"):
                old_setup.setup(start=False)

            _paths, _commands, arm_setup = _fixture(
                Path(directory) / "arm",
                architecture="aarch64",
            )
            with self.assertRaisesRegex(RuntimeError, "allow-experimental"):
                arm_setup.setup(start=False)
            receipt = arm_setup.setup(start=False, allow_experimental=True)
            self.assertTrue(receipt.configured)

    def test_purge_removes_only_fam_user_data_after_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, _commands, setup = _fixture(Path(directory))
            for target in (
                paths.data_home / "fam-os",
                paths.config_home / "fam-os",
                paths.cache_home / "fam-os",
                paths.state_home / "fam-os",
                paths.runtime_dir / "fam-os",
            ):
                target.mkdir(parents=True, exist_ok=True)
                (target / "evidence").write_text("preserved until purge")
            paths.usage_root.mkdir(parents=True)
            (paths.usage_root / "fam.json").write_text("{}")
            sibling = paths.data_home / "keep-me"
            sibling.mkdir(parents=True)

            with self.assertRaisesRegex(PermissionError, "purge requires"):
                setup.purge_user_data(confirmed=False)
            receipt = setup.purge_user_data(confirmed=True)

            self.assertTrue(receipt["purged"])
            self.assertTrue(sibling.is_dir())
            self.assertFalse((paths.data_home / "fam-os").exists())
            self.assertFalse((paths.usage_root / "fam.json").exists())

    def test_purge_refuses_symlink_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, _commands, setup = _fixture(Path(directory))
            outside = Path(directory) / "outside"
            outside.mkdir()
            paths.cache_home.mkdir(parents=True)
            (paths.cache_home / "fam-os").symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(PermissionError, "symbolic link"):
                setup.purge_user_data(confirmed=True)
            self.assertTrue(outside.is_dir())


if __name__ == "__main__":
    unittest.main()
