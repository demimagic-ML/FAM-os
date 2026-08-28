import os
import tempfile
import unittest
from pathlib import Path

from fam_os.console.contracts import REQUIRED_SECTIONS
from fam_os.console.provider import LocalConsoleProvider
from fam_os.console.service import load_or_create_token, rotate_token


class ConsoleContractTests(unittest.TestCase):
    def test_snapshot_always_exposes_every_product_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = LocalConsoleProvider(Path(directory), "v1").snapshot()
        self.assertEqual(tuple(section.section_id for section in snapshot.sections),
                         REQUIRED_SECTIONS)
        self.assertEqual(snapshot.owner_uid, os.geteuid())

    def test_console_token_is_stable_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "runtime", "token")
            first = load_or_create_token(path)
            second = load_or_create_token(path)
            self.assertEqual(first, second)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_widget_token_rotates_atomically_and_rejects_symlink_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "runtime", "widget.token")
            first = rotate_token(path)
            second = rotate_token(path)
            self.assertNotEqual(first, second)
            self.assertEqual(path.read_text().strip(), second)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.unlink()
            outside = Path(directory, "outside")
            outside.write_text("untouched")
            path.symlink_to(outside)
            with self.assertRaisesRegex(PermissionError, "symbolic link"):
                rotate_token(path)
            self.assertEqual(outside.read_text(), "untouched")


if __name__ == "__main__":
    unittest.main()
