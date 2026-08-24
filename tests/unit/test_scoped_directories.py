import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.linux.scoped_directories import (
    ScopedDirectoryAdapter, ScopedDirectoryPolicy,
)


class ScopedDirectoryAdapterTests(unittest.TestCase):
    def test_create_and_exact_empty_reversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter = ScopedDirectoryAdapter(ScopedDirectoryPolicy((root,)))
            target = root / "created"

            created = adapter.create(adapter.prepare_create("create-1", target))
            self.assertTrue(created.exists)
            self.assertTrue(created.empty)
            self.assertEqual(0o700, target.stat().st_mode & 0o777)

            removed = adapter.remove_empty(adapter.prepare_remove(
                "remove-1", target, created.device, created.inode,
            ))
            self.assertFalse(removed.exists)

    def test_reversal_refuses_nonempty_or_replaced_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter = ScopedDirectoryAdapter(ScopedDirectoryPolicy((root,)))
            target = root / "created"
            created = adapter.create(adapter.prepare_create("create-2", target))
            (target / "keep.txt").write_text("owner data")

            with self.assertRaisesRegex(RuntimeError, "precondition"):
                adapter.prepare_remove(
                    "remove-2", target, created.device, created.inode,
                )
            self.assertTrue(target.is_dir())

    def test_out_of_scope_and_symlink_parent_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            approved = root / "approved"
            outside = root / "outside"
            approved.mkdir()
            outside.mkdir()
            (approved / "link").symlink_to(outside, target_is_directory=True)
            adapter = ScopedDirectoryAdapter(ScopedDirectoryPolicy((approved,)))

            with self.assertRaises(PermissionError):
                adapter.prepare_create("outside", outside / "created")
            with self.assertRaises(OSError):
                adapter.prepare_create("symlink", approved / "link" / "created")

    def test_root_and_child_listing_are_bounded_without_following_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "alpha").mkdir()
            (root / "note.txt").write_text("local")
            (root / "link").symlink_to(root / "alpha", target_is_directory=True)
            adapter = ScopedDirectoryAdapter(ScopedDirectoryPolicy((root,)))

            observed = adapter.observe(root)
            listing = adapter.list_entries(root, maximum_entries=2)

            self.assertTrue(observed.exists)
            self.assertFalse(observed.empty)
            self.assertTrue(listing.truncated)
            self.assertEqual(("alpha", "link"), tuple(
                item.name for item in listing.entries
            ))
            self.assertEqual(("directory", "symlink"), tuple(
                item.kind for item in listing.entries
            ))


if __name__ == "__main__":
    unittest.main()
