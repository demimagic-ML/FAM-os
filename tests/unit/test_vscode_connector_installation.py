import json
import tempfile
import unittest
from pathlib import Path

from fam_os.product.vscode_installation import VsCodeConnectorInstallation
from fam_os.product.vscode_package import VSIX_NAME, build_vscode_vsix


class VsCodeConnectorInstallationTests(unittest.TestCase):
    def test_install_discover_update_and_remove(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = root / "release"
            _write_vsix(root, release, "0.1.0")
            manager = VsCodeConnectorInstallation(release, root / "extensions")
            installed = manager.install()
            self.assertTrue(installed.installed)
            self.assertEqual(installed, manager.status())
            _write_vsix(root, release, "0.2.0")
            updated = manager.update()
            self.assertEqual(updated.version, "0.2.0")
            self.assertFalse(Path(installed.path).exists())
            self.assertEqual(updated, manager.update())
            self.assertFalse(manager.remove().installed)

    def test_failed_update_keeps_current_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = root / "release"
            _write_vsix(root, release, "0.1.0")
            manager = VsCodeConnectorInstallation(release, root / "extensions")
            installed = manager.install()
            (release / "share/connector" / VSIX_NAME).write_bytes(b"invalid")
            with self.assertRaises(Exception):
                manager.update()
            self.assertEqual(manager.status(), installed)

    def test_same_version_update_atomically_replaces_changed_connector(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = root / "release"
            _write_vsix(root, release, "0.1.0", "exports.value = 'first';\n")
            manager = VsCodeConnectorInstallation(release, root / "extensions")
            installed = manager.install()

            _write_vsix(root, release, "0.1.0", "exports.value = 'second';\n")
            updated = manager.update()

            self.assertNotEqual(installed.source_digest, updated.source_digest)
            self.assertEqual(
                "exports.value = 'second';\n",
                (Path(updated.path) / "out/extension.js").read_text(),
            )

    def test_remove_preserves_forged_or_unmanaged_marker_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extensions = root / "extensions"
            target = extensions / "fam-os.fam-os-vscode-connector-9.9.9"
            target.mkdir(parents=True)
            (target / ".fam-os-connector.json").write_text(json.dumps({
                "extension_id": "someone-else.unmanaged",
                "version": "9.9.9",
                "source_digest": "0" * 64,
            }), encoding="utf-8")
            manager = VsCodeConnectorInstallation(root / "release", extensions)

            self.assertFalse(manager.remove().installed)
            self.assertTrue(target.is_dir())


def _write_vsix(
    root: Path, release: Path, version: str,
    extension: str = "exports.activate = () => {};\n",
) -> None:
    source = root / f"source-{version}"
    (source / "out").mkdir(parents=True, exist_ok=True)
    (source / "schemas").mkdir(exist_ok=True)
    (source / "package.json").write_text(json.dumps({
        "publisher": "fam-os", "name": "fam-os-vscode-connector",
        "version": version, "main": "./out/extension.js",
    }))
    (source / "out/extension.js").write_text(extension)
    (source / "schemas/vscode.workspace_edit.input.v1.schema.json").write_text("{}\n")
    connector = release / "share/connector"
    connector.mkdir(parents=True, exist_ok=True)
    build_vscode_vsix(source, connector / VSIX_NAME)


if __name__ == "__main__":
    unittest.main()
