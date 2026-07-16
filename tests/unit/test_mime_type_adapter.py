import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.linux.bounded_command import BoundedCommandResult
from fam_os.adapters.linux.mime_types import ScopedMimeTypeAdapter
from fam_os.adapters.linux.scoped_files import ScopedFilePolicy


class MimeTypeAdapterTests(unittest.TestCase):
    def test_magic_result_and_extension_fallback_are_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "note.txt"
            path.write_text("hello")
            runner = Runner(BoundedCommandResult(0, "text/plain\n", ""))
            adapter = ScopedMimeTypeAdapter(
                ScopedFilePolicy((root,)), Path("/usr/bin/file"), runner
            )
            evidence = adapter.observe(path)
            self.assertEqual("text/plain", evidence.mime_type)
            self.assertEqual("magic", evidence.source)
            self.assertEqual("--", runner.command[-2])

            runner.result = BoundedCommandResult(1, "", "private error")
            fallback = adapter.observe(path)
            self.assertEqual("text/plain", fallback.mime_type)
            self.assertEqual("extension_fallback", fallback.source)
            with self.assertRaises(PermissionError):
                adapter.observe(root.parent / "outside.txt")


class Runner:
    def __init__(self, result):
        self.result = result
        self.command = None

    def run(self, command, cwd=None, environment=None):
        self.command = command
        return self.result


if __name__ == "__main__":
    unittest.main()
