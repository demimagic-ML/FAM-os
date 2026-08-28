import json
import os
import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

from fam_os.product.application_test_tools import ApplicationTestTools


ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(
    os.environ.get("FAM_OS_LIVE_OMARCHY_APP") == "1",
    "set FAM_OS_LIVE_OMARCHY_APP=1 on the qualified browser host",
)
class LiveOmarchyApplicationTests(unittest.TestCase):
    def test_build_launch_interact_assert_capture_and_stop_real_browser_app(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "browser-app"
            fixture = Path(os.environ.get(
                "FAM_OS_LIVE_OMARCHY_FIXTURE",
                ROOT / "tests/fixtures/omarchy_browser_app",
            ))
            shutil.copytree(fixture, workspace)
            subprocess.run(
                ("node", "build.mjs"), cwd=workspace, check=True,
                capture_output=True, text=True, timeout=30,
            )
            port = _free_port()
            tools = ApplicationTestTools(
                workspace,
                objective="Build, launch, use, visually capture, and verify the calculator",
            )
            started = json.loads(tools.start({
                "application_id": "fam-browser-e2e",
                "url": f"http://127.0.0.1:{port}/",
                "launch_command": ["node", "server.mjs", str(port)],
                "ready_timeout_seconds": 30,
                "checks": [{
                    "check_id": "result",
                    "kind": "text",
                    "expected": "Result: 7",
                    "description": "Calculator displays the computed result",
                }],
            }))
            self.assertEqual(started["status"], "running")

            snapshot = json.loads(tools.snapshot({}))
            snapshot = json.loads(tools.fill({
                "ref": _ref(snapshot, "First number"), "value": "3",
            }))
            snapshot = json.loads(tools.fill({
                "ref": _ref(snapshot, "Second number"), "value": "4",
            }))
            snapshot = json.loads(tools.click({
                "ref": _ref(snapshot, "Add"),
            }))
            self.assertIn("Result: 7", snapshot["document_text"])

            assertion = tools.assert_outcome({
                "check_id": "result", "kind": "text", "expected": "Result: 7",
            })
            self.assertTrue(assertion.postcondition["verified"])
            console_errors = json.loads(tools.console_errors({}))
            network_failures = json.loads(tools.network_failures({}))
            self.assertEqual(console_errors["count"], 0, console_errors)
            self.assertEqual(network_failures["count"], 0, network_failures)
            self.assertTrue(tools.assert_outcome({
                "check_id": "console_errors", "kind": "console_errors",
                "expected": "0",
            }).postcondition["verified"])
            self.assertTrue(tools.assert_outcome({
                "check_id": "network_failures", "kind": "network_failures",
                "expected": "0",
            }).postcondition["verified"])
            screenshot = tools.screenshot({"name": "verified-calculator"})
            self.assertTrue(screenshot.postcondition["verified"])

            stopped = tools.stop({})
            self.assertTrue(
                stopped.postcondition["verified"],
                {"postcondition": stopped.postcondition, "output": stopped.output},
            )
            summary = json.loads(stopped.output)
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["passed_assertions"], 3)
            self.assertTrue((workspace / summary["trace"]).is_file())


def _ref(snapshot: dict[str, object], name: str) -> str:
    return next(
        item["ref"] for item in snapshot["elements"]
        if item["name"] == name
    )


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


if __name__ == "__main__":
    unittest.main()
