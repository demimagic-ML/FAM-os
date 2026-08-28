import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.product.agent_usage import AgentUsageRepository


ROOT = Path(__file__).resolve().parents[3]


class OmarchyDistributionContractTests(unittest.TestCase):
    def test_plugin_desktop_systemd_and_package_contracts_are_consistent(self):
        manifest = json.loads(
            (ROOT / "integrations/omarchy/plugin/manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["id"], "fam.os")
        self.assertEqual(manifest["name"], "FAM")
        self.assertEqual(manifest["version"], "0.1.1")
        self.assertEqual(manifest["author"], "FAM OS")
        self.assertEqual(manifest["kinds"], ["bar-widget"])
        self.assertEqual(manifest["entryPoints"]["barWidget"], "Widget.qml")
        self.assertNotIn("panel", manifest["entryPoints"])
        self.assertEqual(manifest["barWidget"]["aliases"], ["fam", "fam-goals"])
        widget = (ROOT / "integrations/omarchy/plugin/Widget.qml").read_text()
        panel = (ROOT / "integrations/omarchy/plugin/Panel.qml").read_text()
        self.assertIn("BarWidget {", widget)
        self.assertIn('source: Qt.resolvedUrl("Panel.qml")', widget)
        self.assertIn("Panel {", panel)
        self.assertIn("KeyboardPanel {", panel)
        self.assertNotIn("PanelWindow", widget + panel)
        package = (ROOT / "packaging/arch/PKGBUILD").read_text(encoding="utf-8")
        self.assertIn("arch=('x86_64' 'aarch64')", package)
        self.assertIn("options=('docs')", package)
        self.assertNotIn("pip install", package)
        self.assertNotIn(".venv", package)
        omarchy_package = (
            ROOT / "packaging/omarchy/omarchy-pkgs/fam-os/PKGBUILD"
        ).read_text(encoding="utf-8")
        self.assertIn("arch=('x86_64')", omarchy_package)
        self.assertNotIn("aarch64", omarchy_package)
        matrix = json.loads(
            (ROOT / "packaging/omarchy/support-matrix.json").read_text(encoding="utf-8")
        )
        self.assertEqual(matrix["components"]["python"]["tested"], ">=3.12,<3.15")
        desktop = (ROOT / "packaging/desktop/fam-os.desktop").read_text(
            encoding="utf-8"
        )
        self.assertIn("Exec=fam-os console", desktop)
        self.assertIn("Icon=fam-os", desktop)
        bridge = (ROOT / "packaging/systemd/fam-os-desktop.service").read_text(
            encoding="utf-8"
        )
        self.assertIn("After=graphical-session.target", bridge)
        self.assertIn("PartOf=graphical-session.target", bridge)
        usage = (ROOT / "packaging/systemd/fam-os-usage.service").read_text()
        self.assertIn("/omarchy/agents/usage/fam.json", usage)
        self.assertNotIn("/omarchy/agents/usage/fam-os.json", usage)
        bootstrap = (ROOT / "packaging/omarchy/bootstrap.sh").read_text()
        self.assertIn("EFBCEDEEC8C1C058C5AA64F97D8D854748E4D62A", bootstrap)
        self.assertIn("SHA256SUMS.asc", bootstrap)
        self.assertIn("$package_name.sig", bootstrap)
        self.assertIn("pacman-key --lsign-key", bootstrap)
        self.assertIn("setup omarchy --yes", bootstrap)
        self.assertIn("purge --user-data --yes", bootstrap)
        self.assertIn('sub(/^\\.\\//, "", name)', bootstrap)

        updater = (
            ROOT / "packaging/omarchy/omarchy-pkgs/fam-os/.omarchy/upstream.sh"
        ).read_text()
        self.assertIn('sub(/^\\.\\//, "", name)', updater)
        for package in (package, omarchy_package):
            self.assertIn("integrations/omarchy/menu/omarchy-menu.json", package)
            self.assertIn("integrations/omarchy/hooks/fam-os", package)

    def test_release_scripts_are_executable_and_do_not_embed_an_owner_path(self):
        for relative in (
            "integrations/omarchy/launcher/omarchy-fam",
            "integrations/omarchy/usage-collector/omarchy-agent-usage-fam",
            "integrations/omarchy/hooks/fam-os",
            "packaging/omarchy/bootstrap.sh",
            "packaging/omarchy/sync-package-source.sh",
            "tools/omarchy/source-archive.sh",
            "tools/omarchy/vm-e2e.sh",
        ):
            path = ROOT / relative
            self.assertTrue(os.access(path, os.X_OK), relative)
            self.assertNotIn("/home/", path.read_text(encoding="utf-8"), relative)

    def test_usage_record_matches_the_dynamic_omarchy_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = AgentUsageRepository(Path(directory) / "usage.sqlite3")
            repository.add("codex-subscription", "gpt-5.4", 100, 25, 2.5)
            record = repository.omarchy_record(
                datetime.now(timezone.utc),
                goals={"total": 2, "active": 1, "completed": 1, "failed": 0},
            )
        required = {
            "schemaVersion",
            "id",
            "name",
            "updatedAt",
            "ready",
            "todayPrompts",
            "todaySessions",
            "todayTotalTokens",
            "todayTokensByModel",
            "recentDays",
            "totalPrompts",
            "totalSessions",
            "activeDays",
            "activeDates",
            "modelUsage",
            "limits",
        }
        self.assertTrue(required.issubset(record))
        self.assertEqual(record["id"], "fam-os")
        self.assertEqual(record["goalCount"], 2)
        self.assertEqual(record["inferenceLocation"]["hostedTokens"], 125)


if __name__ == "__main__":
    unittest.main()
