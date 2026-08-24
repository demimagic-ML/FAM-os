import tempfile
import unittest
from pathlib import Path

from fam_os.console.workspaces import ConsoleWorkspaceApi


class ConsoleWorkspaceApiTests(unittest.TestCase):
    def test_browse_returns_bounded_folder_and_file_choices(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            (project / "src").mkdir()
            (project / "README.md").write_text("local")

            document = ConsoleWorkspaceApi(root).browse(str(project))

            self.assertEqual(str(project), document["path"])
            self.assertTrue(document["uri"].endswith("/project/"))
            self.assertEqual(("src", "README.md"), tuple(
                item["name"] for item in document["entries"]
            ))
            self.assertEqual(("directory", "file"), tuple(
                item["kind"] for item in document["entries"]
            ))

    def test_outside_and_symlink_directories_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            approved = root / "approved"
            outside = root / "outside"
            approved.mkdir()
            outside.mkdir()
            (approved / "link").symlink_to(outside, target_is_directory=True)
            api = ConsoleWorkspaceApi(approved)

            with self.assertRaises(PermissionError):
                api.browse(str(outside))
            with self.assertRaises(PermissionError):
                api.browse(str(approved / "link"))


if __name__ == "__main__":
    unittest.main()
