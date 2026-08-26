import importlib.util
import json
import socket
import shutil
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fam_os.core.agent import AgentAuthorityProfile, AgentToolCall, AgentToolRegistry
from fam_os.product.application_test_tools import ApplicationTestTools
from fam_os.product.application_test_tools import PlaywrightBrowserDriver


FIXTURE = Path(__file__).parents[1] / "fixtures/application_test"


@unittest.skipUnless(
    importlib.util.find_spec("playwright.sync_api") is not None
    and any(shutil.which(item) for item in ("google-chrome", "chromium", "chromium-browser")),
    "Playwright and a local Chromium browser are required",
)
class PlaywrightApplicationTestIntegrationTests(unittest.TestCase):
    def test_full_harness_launches_sandboxed_app_and_verifies_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(FIXTURE / "calculator.html", root / "calculator.html")
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            registry = AgentToolRegistry()
            tools = ApplicationTestTools(
                root, objective="Test calculator operations",
            )
            tools.register(registry)
            profile = AgentAuthorityProfile.APPLICATION_TEST
            started = registry.invoke(AgentToolCall(
                "start", "app_start", {
                    "application_id": "calculator",
                    "url": f"http://127.0.0.1:{port}/calculator.html",
                    "launch_command": [
                        "python3", "-m", "http.server", str(port),
                        "--bind", "127.0.0.1",
                    ],
                    "checks": [{
                        "check_id": "addition", "kind": "text",
                        "description": "Addition returns twelve.", "expected": "12",
                    }],
                }, "Launch the candidate application.",
            ), profile)
            self.assertTrue(started.succeeded, started.output)
            snapshot = json.loads(started.output)["current_snapshot"]
            add = next(
                item for item in snapshot["elements"]
                if item["name"] == "Add seven and five"
            )
            clicked = registry.invoke(AgentToolCall(
                "click", "app_click", {"ref": add["ref"]}, "Add values.",
            ), profile)
            self.assertTrue(clicked.succeeded, clicked.output)
            for index, check in enumerate((
                {"check_id": "addition", "kind": "text", "expected": "12"},
                {"check_id": "console_errors", "kind": "console_errors", "expected": "0"},
                {"check_id": "network_failures", "kind": "network_failures", "expected": "0"},
            ), 1):
                assertion = registry.invoke(AgentToolCall(
                    f"assert-{index}", "app_assert", check,
                    "Verify retained application evidence.",
                ), profile)
                self.assertTrue(assertion.postcondition["verified"], assertion.output)
            stopped = registry.invoke(AgentToolCall(
                "stop", "app_stop", {}, "Finalize evidence and clean up.",
            ), profile)
            self.assertTrue(stopped.postcondition["verified"], stopped.output)
            self.assertIsNotNone(tools.session.process_id)
            self.assertEqual("completed", tools.session.status)
            self.assertIsNone(tools._process)

    def test_structured_snapshot_action_diagnostics_screenshot_and_trace(self):
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            lambda *args, **kwargs: SimpleHTTPRequestHandler(
                *args, directory=str(FIXTURE), **kwargs,
            ),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        driver = PlaywrightBrowserDriver()
        artifacts = FIXTURE / ".test-artifacts"
        artifacts.mkdir(exist_ok=True)
        try:
            driver.start(
                f"http://127.0.0.1:{server.server_port}/calculator.html",
                artifacts,
            )
            snapshot = driver.snapshot()
            add = next(
                item for item in snapshot["elements"]
                if item["name"] == "Add seven and five"
            )
            changed = driver.click(add["ref"])
            self.assertIn("12", changed["document_text"])
            self.assertEqual((), driver.console_errors())
            self.assertEqual((), driver.network_failures())
            screenshot = artifacts / "final.png"
            trace = artifacts / "trace.zip"
            driver.screenshot(screenshot)
            stopped = driver.stop(trace)
            self.assertGreater(screenshot.stat().st_size, 0)
            self.assertGreater(trace.stat().st_size, 0)
            self.assertGreater(Path(stopped["video"]).stat().st_size, 0)
        finally:
            try:
                driver.stop(artifacts / "cleanup-trace.zip")
            except Exception:
                pass
            server.shutdown()
            server.server_close()
            thread.join()
            for path in sorted(artifacts.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            artifacts.rmdir()


if __name__ == "__main__":
    unittest.main()
