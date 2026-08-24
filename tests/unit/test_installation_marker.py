import json
import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.installation_marker import (
    MARKER_NAME,
    ExpectedManagedFile,
    load_installation_marker,
    managed_file_issues,
    write_installation_marker,
)
from fam_os.product.linux_installation import INSTALL_CONTRACT_VERSION


class InstallationMarkerTests(unittest.TestCase):
    def test_expected_file_ledger_detects_deletion_and_digest_damage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary)
            launcher = prefix / "bin/fam-shell"
            launcher.parent.mkdir(mode=0o700)
            launcher.write_text("trusted launcher\n", encoding="utf-8")

            write_installation_marker(prefix, "release-1", (launcher,))
            marker = load_installation_marker(prefix)
            self.assertEqual((), managed_file_issues(prefix, marker))

            launcher.unlink()
            self.assertEqual(
                ("managed_file_missing:bin/fam-shell",),
                managed_file_issues(prefix, marker),
            )
            launcher.write_text("tampered launcher\n", encoding="utf-8")
            self.assertEqual(
                ("managed_file_digest_mismatch:bin/fam-shell",),
                managed_file_issues(prefix, marker),
            )

    def test_legacy_path_ledger_requires_digest_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary)
            launcher = prefix / "bin/fam-os"
            launcher.parent.mkdir(mode=0o700)
            launcher.write_text("legacy\n", encoding="utf-8")
            marker_path = prefix / MARKER_NAME
            marker_path.write_text(json.dumps({
                "contract_version": INSTALL_CONTRACT_VERSION,
                "release_id": "legacy-release",
                "managed_files": ["bin/fam-os"],
            }), encoding="utf-8")
            os.chmod(marker_path, 0o600)

            marker = load_installation_marker(prefix)
            self.assertTrue(marker.legacy_unhashed)
            self.assertEqual(
                ("installation_marker_upgrade_required",),
                managed_file_issues(prefix, marker),
            )

    def test_marker_rejects_paths_outside_managed_installation_surfaces(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the installation contract"):
            ExpectedManagedFile("releases/release-1", "0" * 64)


if __name__ == "__main__":
    unittest.main()
