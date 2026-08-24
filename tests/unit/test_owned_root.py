import json
import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.owned_root import MARKER, OwnedProductRoot


class OwnedProductRootTests(unittest.TestCase):
    def test_owner_bound_marker_authorizes_complete_root_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "state"
            root.mkdir(mode=0o700)
            owned = OwnedProductRoot(root, "state", os.geteuid())
            owned.initialize()
            (root / "database.sqlite3").write_text("durable", encoding="utf-8")

            marker = json.loads((root / MARKER).read_text(encoding="utf-8"))
            self.assertEqual(str(root.resolve()), marker["root"])
            self.assertTrue(owned.remove())
            self.assertFalse(root.exists())

    def test_unmarked_root_is_never_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "state"
            root.mkdir(mode=0o700)

            with self.assertRaisesRegex(FileNotFoundError, "marker"):
                OwnedProductRoot(root, "state", os.geteuid()).remove()
            self.assertTrue(root.is_dir())

    def test_marker_cannot_be_reused_for_a_different_purpose(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "state"
            root.mkdir(mode=0o700)
            OwnedProductRoot(root, "state", os.geteuid()).initialize()

            with self.assertRaisesRegex(PermissionError, "does not match"):
                OwnedProductRoot(root, "runtime", os.geteuid()).verify()


if __name__ == "__main__":
    unittest.main()
