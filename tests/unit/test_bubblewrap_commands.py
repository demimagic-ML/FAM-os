import unittest

from fam_os.adapters.bubblewrap.commands import (
    build_bubblewrap_command,
    build_python_command,
)
from fam_os.adapters.bubblewrap.settings import BubblewrapSettings


class BubblewrapCommandTests(unittest.TestCase):
    def test_builds_isolated_python_command(self) -> None:
        command = build_bubblewrap_command(
            "/usr/bin/bwrap", "/usr/bin/python3", "print('test')", BubblewrapSettings()
        )
        self.assertEqual(command[0], "/usr/bin/bwrap")
        self.assertIn("--unshare-all", command)
        self.assertIn("--die-with-parent", command)
        self.assertIn("--cap-drop", command)
        self.assertIn("--ro-bind", command)
        self.assertIn("--tmpfs", command)
        self.assertEqual(command[-4:], ("-I", "-S", "-c", "print('test')"))

    def test_builds_explicit_process_fallback_command(self) -> None:
        self.assertEqual(
            build_python_command("/usr/bin/python3", "pass"),
            ("/usr/bin/python3", "-I", "-S", "-c", "pass"),
        )


if __name__ == "__main__":
    unittest.main()
