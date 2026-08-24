import unittest

from fam_os.adapters.bubblewrap.commands import (
    build_bubblewrap_command,
    build_python_command,
    build_systemd_sandbox_command,
)
from fam_os.adapters.bubblewrap.settings import BubblewrapSettings
from fam_os.verification import SandboxLimits


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

    def test_apparmor_uses_manager_launched_transient_verifier_service(self) -> None:
        command = build_systemd_sandbox_command(
            "/usr/bin/systemd-run", ("/usr/bin/bwrap", "--unshare-all"),
            SandboxLimits(), "fam-os-userns",
        )

        self.assertNotIn("--scope", command)
        self.assertIn("--pipe", command)
        self.assertIn("--wait", command)
        self.assertIn("--collect", command)
        self.assertIn("--service-type=exec", command)
        self.assertIn("AppArmorProfile=fam-os-userns", command)
        self.assertEqual(command[-2:], ("/usr/bin/bwrap", "--unshare-all"))

    def test_rejects_unsafe_apparmor_profile_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "profile name"):
            BubblewrapSettings(apparmor_profile="--property=RootDirectory=/")


if __name__ == "__main__":
    unittest.main()
