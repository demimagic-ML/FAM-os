import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.linux.scoped_files import ScopedFileAdapter, ScopedFilePolicy


class ScopedFileAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.adapter = ScopedFileAdapter(ScopedFilePolicy(
            (self.root,), maximum_read_bytes=100, maximum_write_bytes=100
        ))

    def test_observe_is_bounded_and_content_is_opt_in(self):
        path = self.root / "document.txt"
        path.write_bytes(b"hello")
        metadata = self.adapter.observe(path)
        content = self.adapter.observe(path, include_content=True)
        self.assertIsNone(metadata.content)
        self.assertEqual(b"hello", content.content)
        self.assertEqual(64, len(content.sha256))
        path.write_bytes(b"x" * 101)
        with self.assertRaisesRegex(ValueError, "bounded"):
            self.adapter.observe(path)

    def test_prepare_apply_checks_content_and_changed_precondition(self):
        path = self.root / "document.txt"
        path.write_bytes(b"before")
        proposal = self.adapter.prepare_write("write-1", path, b"after")
        evidence = self.adapter.apply_write(proposal, b"after")
        self.assertEqual(b"after", path.read_bytes())
        self.assertEqual(proposal.expected_after_sha256, evidence.after_sha256)

        stale = self.adapter.prepare_write("write-2", path, b"next")
        path.write_bytes(b"changed elsewhere")
        with self.assertRaisesRegex(RuntimeError, "precondition"):
            self.adapter.apply_write(stale, b"next")

    def test_scope_symlink_and_path_traversal_reject(self):
        outside = self.root.parent / "outside-fam-test.txt"
        link = self.root / "link"
        link.symlink_to(outside)
        with self.assertRaises(PermissionError):
            self.adapter.observe(link)
        with self.assertRaises(PermissionError):
            self.adapter.observe(outside)
        with self.assertRaises(PermissionError):
            self.adapter.prepare_write("write-1", self.root / ".." / "escape", b"x")

    def test_atomic_create_defaults_to_private_mode(self):
        path = self.root / "new.txt"
        proposal = self.adapter.prepare_write("write-1", path, b"new")
        self.adapter.apply_write(proposal, b"new")
        self.assertEqual(0o600, path.stat().st_mode & 0o777)


if __name__ == "__main__":
    unittest.main()
