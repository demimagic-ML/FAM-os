import unittest

from fam_os.adapters.omarchy.commands import CommandReceipt
from fam_os.adapters.omarchy.snapshots import OmarchySnapshots


class _Runner:
    def __init__(self):
        self.list_calls = 0

    def run(self, command, **_kwargs):
        command = tuple(command)
        if command == (
            "/usr/bin/sudo", "-n", "/usr/bin/snapper",
            "--csvout", "list-configs",
        ):
            return CommandReceipt(command, 0, "Config,Subvolume\nroot,/\n", "")
        if "--columns" in command:
            self.list_calls += 1
            values = "Number\n41\n" if self.list_calls == 1 else "Number\n41\n42\n"
            return CommandReceipt(command, 0, values, "")
        if command == ("/usr/bin/omarchy-snapshot", "create"):
            return CommandReceipt(command, 0, "Snapshots can be selected during boot.", "")
        raise AssertionError(command)


class OmarchySnapshotTests(unittest.TestCase):
    def test_persists_observed_snapper_ids_and_recovery_command(self):
        snapshots = OmarchySnapshots(
            runner=_Runner(), which=lambda name: f"/usr/bin/{name}",
        )

        receipt = snapshots.create("FAM preflight")

        self.assertTrue(receipt.created)
        self.assertEqual(("root:42",), receipt.references)
        self.assertEqual("root:42", receipt.reference)
        self.assertEqual("omarchy snapshot restore", receipt.recovery_command)

    def test_unconfigured_snapper_is_not_reported_as_a_snapshot(self):
        class Empty:
            def run(self, command, **_kwargs):
                return CommandReceipt(tuple(command), 0, "Config,Subvolume\n", "")

        receipt = OmarchySnapshots(
            runner=Empty(), which=lambda name: f"/usr/bin/{name}",
        ).create("FAM preflight")

        self.assertFalse(receipt.created)
        self.assertIn("no configured snapshot roots", receipt.detail)


if __name__ == "__main__":
    unittest.main()
