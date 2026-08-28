import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.omarchy.commands import CommandReceipt
from fam_os.adapters.omarchy.notifications import send_notification
from fam_os.product.omarchy_goal_notifications import OmarchyGoalNotifications


class _Runner:
    def __init__(self):
        self.calls = []

    def run(self, command, **_kwargs):
        self.calls.append(tuple(command))
        return CommandReceipt(tuple(command), 0, "73", "")


class OmarchyNotificationTests(unittest.TestCase):
    def test_native_notification_uses_argv_click_action_and_replacement(self):
        runner = _Runner()

        receipt = send_notification(
            "FAM completed", "Five checks passed", urgency="normal",
            replace_id=72, print_id=True, runner=runner,
            which=lambda name: "/usr/bin/omarchy" if name == "omarchy" else None,
        )

        self.assertTrue(receipt.succeeded)
        self.assertEqual((
            "/usr/bin/omarchy", "notification", "send", "--app-name", "FAM",
            "-u", "normal", "-i", "fam-os", "-r", "72", "-p",
            "FAM completed", "Five checks passed", "--exec", "fam", "console",
        ), runner.calls[0])

    def test_goal_notifications_replace_prior_toast_and_delay_recovery_noise(self):
        calls = []

        def sender(title, message, **kwargs):
            calls.append((title, message, kwargs))
            return CommandReceipt(("notify",), 0, "91", "")

        with tempfile.TemporaryDirectory() as directory:
            notifications = OmarchyGoalNotifications(
                Path(directory) / "ids.json", sender=sender,
            )
            notifications("goal-1", "retry_wait", "Build app", recovery_attempt=2)
            notifications("goal-1", "retry_wait", "Build app", recovery_attempt=3)
            notifications("goal-1", "completed", "Build app", "5 checks passed")

        self.assertEqual(2, len(calls))
        self.assertIsNone(calls[0][2]["replace_id"])
        self.assertEqual(91, calls[1][2]["replace_id"])


if __name__ == "__main__":
    unittest.main()
