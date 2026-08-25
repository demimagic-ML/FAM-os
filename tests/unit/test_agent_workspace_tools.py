import tempfile
import unittest
from pathlib import Path
from subprocess import run

from fam_os.core.agent import AgentAuthorityProfile, AgentToolCall, AgentToolRegistry
from fam_os.product.agent_workspace_tools import WorkspaceAgentTools


class AgentWorkspaceToolsTests(unittest.TestCase):
    def test_plain_folder_does_not_advertise_unusable_git_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = AgentToolRegistry()
            WorkspaceAgentTools(Path(directory)).register(registry)

            identifiers = {item.tool_id for item in registry.descriptors()}

            self.assertNotIn("git_status", identifiers)
            self.assertNotIn("git_diff", identifiers)

            listed = _invoke(registry, "list_directory", {"path": "."})
            self.assertTrue(listed.succeeded)
            self.assertEqual("Directory is empty.", listed.output)

    def test_large_file_is_read_in_bounded_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = "0123456789" * 20
            (root / "large.txt").write_text(content)
            registry = AgentToolRegistry()
            WorkspaceAgentTools(root, maximum_read_bytes=64).register(registry)

            first = _invoke(registry, "read_file", {
                "path": "large.txt", "maximum_bytes": 50,
            })
            second = _invoke(registry, "read_file", {
                "path": "large.txt", "offset_bytes": 50, "maximum_bytes": 50,
            })

            self.assertTrue(first.succeeded, first.output)
            self.assertIn("bytes=0-50/200", first.output)
            self.assertIn("next_offset=50", first.output)
            self.assertIn("bytes=50-100/200", second.output)

    def test_agent_can_discover_create_patch_move_and_delete_without_file_count_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/app.py").write_text("value = 1\n")
            run(("git", "init", "-q"), cwd=root, check=True)
            registry = AgentToolRegistry()
            WorkspaceAgentTools(root).register(registry)

            read = _invoke(registry, "read_file", {"path": "src/app.py"})
            self.assertTrue(read.succeeded)
            self.assertIn("value = 1", read.output)
            created = _invoke(registry, "write_file", {
                "path": "src/new.py", "content": "created = True\n",
                "expected_sha256": None,
            })
            self.assertTrue(created.succeeded)
            self.assertEqual("file", created.postcondition["kind"])
            self.assertTrue(created.postcondition["verified"])
            directory = _invoke(registry, "create_directory", {"path": "reports"})
            self.assertTrue(directory.succeeded)
            self.assertEqual({
                "verified": True, "operation": "create_directory",
                "path": "reports", "exists": True, "kind": "directory",
            }, directory.postcondition)
            patched = _invoke(registry, "apply_patch", {"patch": (
                "diff --git a/src/app.py b/src/app.py\n"
                "--- a/src/app.py\n+++ b/src/app.py\n"
                "@@ -1 +1 @@\n-value = 1\n+value = 2\n"
            )})
            self.assertTrue(patched.succeeded, patched.output)
            moved = _invoke(registry, "move_path", {
                "source": "src/new.py", "destination": "lib/new.py",
            })
            self.assertTrue(moved.succeeded)
            self.assertTrue(moved.postcondition["verified"])
            deleted = _invoke(registry, "delete_path", {"path": "lib/new.py"})
            self.assertTrue(deleted.succeeded)
            self.assertTrue(deleted.postcondition["verified"])
            self.assertEqual("value = 2\n", (root / "src/app.py").read_text())

    def test_workspace_profile_blocks_escape_and_symlink_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            outside = Path(directory) / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "link").symlink_to(outside, target_is_directory=True)
            registry = AgentToolRegistry()
            WorkspaceAgentTools(root).register(registry)

            escaped = _invoke(registry, "write_file", {
                "path": "../outside/x", "content": "x", "expected_sha256": None,
            })
            linked = _invoke(registry, "write_file", {
                "path": "link/x", "content": "x", "expected_sha256": None,
            })

            self.assertFalse(escaped.succeeded)
            self.assertFalse(linked.succeeded)
            self.assertFalse((outside / "x").exists())

    def test_absolute_paths_inside_selected_workspace_are_canonicalized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            reports = root / "reports"
            reports.mkdir(parents=True)
            registry = AgentToolRegistry()
            WorkspaceAgentTools(root).register(registry)

            listed_root = _invoke(
                registry, "list_directory", {"path": root.as_posix()},
            )
            created = _invoke(registry, "write_file", {
                "path": (reports / "alpha.txt").as_posix(),
                "content": "ALPHA", "expected_sha256": None,
            })

            self.assertTrue(listed_root.succeeded, listed_root.output)
            self.assertIn("directory\treports", listed_root.output)
            self.assertTrue(created.succeeded, created.output)
            self.assertEqual("reports/alpha.txt", created.postcondition["path"])
            self.assertEqual("ALPHA", (reports / "alpha.txt").read_text())

    def test_absolute_path_outside_selected_workspace_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            outside = Path(directory) / "outside"
            root.mkdir()
            outside.mkdir()
            registry = AgentToolRegistry()
            WorkspaceAgentTools(root).register(registry)

            escaped = _invoke(registry, "write_file", {
                "path": (outside / "x").as_posix(),
                "content": "x", "expected_sha256": None,
            })

            self.assertFalse(escaped.succeeded)
            self.assertIn("must stay inside", escaped.output)
            self.assertFalse((outside / "x").exists())


def _invoke(registry, tool, arguments):
    return registry.invoke(
        AgentToolCall("call", tool, arguments, "test"),
        AgentAuthorityProfile.WORKSPACE,
    )


if __name__ == "__main__":
    unittest.main()
