import json
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.linux.accessibility.types import (
    ProviderAccessibleAction, ProviderAccessibleNode,
)
from fam_os.adapters.linux.x11_windows import WindowDiscoveryResult
from fam_os.adapters.omarchy.commands import CommandReceipt
from fam_os.applications import ApplicationWindow
from fam_os.product.native_application_test_tools import NativeApplicationTestTools


class _Launcher:
    def __init__(self):
        self.commands = []

    def launch(self, command):
        self.commands.append(tuple(command))
        return CommandReceipt(("uwsm-app", "--", *command), 0, "123", "")


class _Discovery:
    def __init__(self):
        self.calls = 0

    def discover(self):
        self.calls += 1
        windows = () if self.calls == 1 else (
            ApplicationWindow("0xabc", 999_999, "org.example.Calculator", "Calculator"),
        )
        return WindowDiscoveryResult(windows, None, ())


class _Provider:
    def __init__(self):
        self.performed = None
        action = ProviderAccessibleAction(0, "click")
        self.nodes = {
            "root": ProviderAccessibleNode(
                999_999, "application", "Calculator", None, ("enabled",),
                (), "Calculator 2 + 2", False, 1,
            ),
            "button": ProviderAccessibleNode(
                999_999, "push button", "Equals", None, ("enabled",),
                (action,), "=", False, 0,
            ),
        }

    def available(self):
        return True

    def roots(self):
        return ("root",)

    def read(self, handle, _maximum, include_text=False):
        value = self.nodes[handle]
        if include_text:
            return value
        return ProviderAccessibleNode(
            value.process_id, value.role, value.name, value.description,
            value.states, value.actions, None, value.protected,
            value.child_count, value.text_truncated,
        )

    def child(self, handle, index):
        return "button" if handle == "root" and index == 0 else None

    def perform_action(self, handle, action_index):
        self.performed = (handle, action_index)
        return True


class NativeApplicationTestToolTests(unittest.TestCase):
    def test_session_launches_observes_acts_asserts_and_persists_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = _Provider()
            launcher = _Launcher()
            tools = NativeApplicationTestTools(
                root, launcher=launcher, discovery=_Discovery(),
                provider_factory=lambda: provider, sleeper=lambda _seconds: None,
            )

            started = json.loads(tools.start({
                "application_id": "calculator", "command": ["calculator"],
                "timeout_seconds": 1,
            }))
            reference = next(
                item["ref"] for item in started["nodes"]
                if item["name"] == "Equals"
            )
            action = tools.action({"ref": reference, "action": "click"})
            assertion = tools.assert_outcome({
                "kind": "text", "expected": "Calculator", "ref": "",
            })
            stopped = tools.stop({})

            self.assertEqual([("calculator",)], launcher.commands)
            self.assertEqual(("button", 0), provider.performed)
            self.assertTrue(action.postcondition["verified"])
            self.assertTrue(assertion.postcondition["verified"])
            self.assertTrue(stopped.postcondition["verified"])
            evidence = root / tools.summary["artifact_root"] / "session.json"
            self.assertTrue(evidence.is_file())
            self.assertEqual(0o600, evidence.stat().st_mode & 0o777)


if __name__ == "__main__":
    unittest.main()
