import unittest

from fam_os.adapters.systemd.commands import (
    build_show_command,
    build_reset_failed_command,
    build_start_command,
    build_stop_command,
)
from fam_os.adapters.systemd.settings import SystemdUserSettings
from fam_os.supervisor import BlockIoBandwidthLimit, ResourceLimits, ServiceDefinition


class SystemdCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = SystemdUserSettings("/bin/systemctl", "/bin/systemd-run", 3)

    def test_builds_bounded_user_transient_service(self) -> None:
        definition = ServiceDefinition(
            "fam-test",
            ("/usr/bin/sleep", "30"),
            (("FAM_MODE", "smoke"),),
            ResourceLimits(16_777_216, 0, 50.5, 32),
        )
        command = build_start_command(definition, self.settings)
        self.assertEqual(command[:4], (
            "/bin/systemd-run", "--user", "--unit=fam-test.service", "--collect"
        ))
        self.assertIn("--property=MemoryMax=16777216", command)
        self.assertIn("--property=MemorySwapMax=0", command)
        self.assertIn("--property=CPUQuota=50.5%", command)
        self.assertIn("--property=TasksMax=32", command)
        self.assertIn("--property=KillMode=control-group", command)
        self.assertIn("--property=SendSIGKILL=yes", command)
        self.assertIn("--property=TimeoutStopSec=3s", command)
        self.assertIn("--setenv=FAM_MODE=smoke", command)
        self.assertEqual(command[-2:], ("/usr/bin/sleep", "30"))
        self.assertEqual("--", command[-3])

    def test_command_options_cannot_escape_the_argument_boundary(self) -> None:
        definition = ServiceDefinition("fam-test", ("--property=User=root",))
        command = build_start_command(definition, self.settings)
        self.assertEqual(("--", "--property=User=root"), command[-2:])

    def test_applies_explicit_block_io_bandwidth(self) -> None:
        limits = ResourceLimits(block_io_bandwidth=(
            BlockIoBandwidthLimit("/dev/nvme0n1", 259, 0, 1_000_000_000, 256_000_000),
        ))
        command = build_start_command(
            ServiceDefinition("fam-test", ("/usr/bin/true",), limits=limits),
            self.settings,
        )
        self.assertIn(
            "--property=IOReadBandwidthMax=/dev/nvme0n1 1000000000", command
        )
        self.assertIn(
            "--property=IOWriteBandwidthMax=/dev/nvme0n1 256000000", command
        )

    def test_applies_explicit_apparmor_profile(self) -> None:
        settings = SystemdUserSettings(apparmor_profile="fam-os-supervisor")
        command = build_start_command(
            ServiceDefinition("fam-test", ("/usr/bin/true",)), settings
        )
        self.assertIn("--property=AppArmorProfile=fam-os-supervisor", command)

    def test_can_retain_failed_state_until_recovery(self) -> None:
        settings = SystemdUserSettings(retain_failed_state=True)
        command = build_start_command(
            ServiceDefinition("fam-test", ("/usr/bin/false",)), settings
        )
        self.assertIn("--property=CollectMode=inactive", command)
        self.assertNotIn("--collect", command)

    def test_rejects_invalid_apparmor_profile(self) -> None:
        with self.assertRaisesRegex(ValueError, "AppArmor"):
            SystemdUserSettings(apparmor_profile="bad profile")

    def test_builds_user_scoped_stop(self) -> None:
        self.assertEqual(
            build_stop_command("fam-test", self.settings),
            ("/bin/systemctl", "--user", "stop", "fam-test.service"),
        )

    def test_builds_user_scoped_failed_state_reset(self) -> None:
        self.assertEqual(
            build_reset_failed_command("fam-test", self.settings),
            ("/bin/systemctl", "--user", "reset-failed", "fam-test.service"),
        )

    def test_show_requests_only_known_properties(self) -> None:
        command = build_show_command("fam-test.service", self.settings)
        self.assertEqual(command[:4], (
            "/bin/systemctl", "--user", "show", "fam-test.service"
        ))
        self.assertEqual(command[-1], "--no-pager")
        self.assertIn("--property=ControlGroup", command)


if __name__ == "__main__":
    unittest.main()
