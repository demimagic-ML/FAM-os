import os
import tempfile
import unittest
from pathlib import Path

from fam_os.console.contracts import REQUIRED_SECTIONS
from fam_os.console.provider import LocalConsoleProvider
from fam_os.console.service import load_or_create_token


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


if __name__ == "__main__":
    unittest.main()
