import json
import sys
import unittest
from pathlib import Path

from fam_os.adapters.linux.bounded_command import BoundedCommandResult
from fam_os.adapters.linux.dbus_calls import (
    AllowlistedDbusAdapter, DbusBus, DbusCapabilitySpec, DbusParameter,
)
from fam_os.adapters.linux.desktop_portal import (
    DesktopPortalAdapter, PortalOpenUriPolicy,
)
from fam_os.adapters.linux.tools import (
    AllowlistedToolAdapter, ToolCapabilitySpec, ToolOutputKind, ToolParameter,
)


class DbusCapabilityTests(unittest.TestCase):
    def test_allowlisted_schema_checked_call_is_shell_free_and_safe_on_failure(self):
        runner = Runner(BoundedCommandResult(0, "s success\n", ""))
        adapter = AllowlistedDbusAdapter((_dbus_spec(),), runner=runner)
        outcome = adapter.invoke("dbus.echo", {"message": "$(touch never)"})
        self.assertTrue(outcome.succeeded)
        self.assertEqual("$(touch never)", runner.command[-1])
        self.assertIsInstance(runner.command, tuple)
        with self.assertRaises(PermissionError):
            adapter.invoke("dbus.other", {})
        with self.assertRaisesRegex(ValueError, "schema"):
            adapter.invoke("dbus.echo", {})

        runner.result = BoundedCommandResult(1, "", "private bus detail")
        failed = adapter.invoke("dbus.echo", {"message": "x"})
        self.assertEqual("dbus.call_failed", failed.error_code)
        self.assertNotIn("private", str(failed.output))


class ToolCapabilityTests(unittest.TestCase):
    def test_exact_tool_mapping_json_output_and_no_arbitrary_capability(self):
        runner = Runner(BoundedCommandResult(0, json.dumps({"count": 2}), ""))
        adapter = AllowlistedToolAdapter((_tool_spec(),), runner)
        result = adapter.invoke("tool.count", {"path": "$(touch never)", "verbose": True})
        self.assertTrue(result.succeeded)
        self.assertEqual(
            (sys.executable, "fixed.py", "--path", "$(touch never)", "--verbose"),
            runner.command,
        )
        self.assertEqual(2, result.output["json"]["count"])
        with self.assertRaises(PermissionError):
            adapter.invoke("tool.unlisted", {})

    def test_invalid_output_and_failed_process_are_content_free(self):
        runner = Runner(BoundedCommandResult(0, "not-json", ""))
        adapter = AllowlistedToolAdapter((_tool_spec(),), runner)
        invalid = adapter.invoke("tool.count", {"path": "x"})
        self.assertEqual("tool.output_invalid", invalid.error_code)
        runner.result = BoundedCommandResult(1, "candidate", "private failure")
        failed = adapter.invoke("tool.count", {"path": "x"})
        self.assertEqual("tool.execution_failed", failed.error_code)
        self.assertEqual({}, dict(failed.output))


class DesktopPortalTests(unittest.TestCase):
    def test_uri_is_prepared_separately_then_invoked_as_exact_argument(self):
        runner = Runner(BoundedCommandResult(0, "('/request/1',)\n", ""))
        adapter = DesktopPortalAdapter(
            PortalOpenUriPolicy(("https",), environment=(("LANG", "C.UTF-8"),)),
            runner,
        )
        self.assertTrue(adapter.probe().succeeded)
        proposal = adapter.prepare_open_uri("open-1", "https://example.com/a?q=$(never)")
        result = adapter.open_uri(proposal)
        self.assertTrue(result.succeeded)
        self.assertEqual(proposal.uri, runner.command[-2])
        self.assertEqual("{}", runner.command[-1])
        with self.assertRaises(PermissionError):
            adapter.prepare_open_uri("open-2", "file:///etc/passwd")
        with self.assertRaises(ValueError):
            adapter.prepare_open_uri("open-3", "https://user:secret@example.com")


class Runner:
    def __init__(self, result):
        self.result = result
        self.command = None
        self.cwd = None
        self.environment = None

    def run(self, command, cwd=None, environment=None):
        self.command = command
        self.cwd = cwd
        self.environment = environment
        return self.result


def _dbus_spec():
    return DbusCapabilitySpec(
        "dbus.echo", DbusBus.USER, "org.example.Service", "/org/example/Service",
        "org.example.Service", "Echo", (DbusParameter("message", "s"),),
        {
            "type": "object", "properties": {"message": {"type": "string"}},
            "required": ["message"], "additionalProperties": False,
        },
    )


def _tool_spec():
    return ToolCapabilitySpec(
        "tool.count", Path(sys.executable), ("fixed.py",),
        (ToolParameter("path", "--path"), ToolParameter("verbose", "--verbose", True)),
        {
            "type": "object",
            "properties": {"path": {"type": "string"}, "verbose": {"type": "boolean"}},
            "required": ["path"], "additionalProperties": False,
        },
        ToolOutputKind.JSON,
    )


if __name__ == "__main__":
    unittest.main()
