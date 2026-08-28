import json
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from fam_os.core.agent import (
    AgentAuthorityProfile, AgentToolCall, AgentToolRegistry,
    ApplicationTestingObjectiveCompiler,
)
from fam_os.product.application_test_tools import (
    ApplicationTestTools, PlaywrightBrowserDriver,
    _sandboxed_application_command,
)


class ApplicationTestToolsTests(unittest.TestCase):
    def test_sandbox_projects_a_non_system_toolchain_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            executable = root / "toolchains/node/24/bin/node"
            workspace.mkdir()
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"node")
            with patch(
                "fam_os.product.application_test_tools.shutil.which",
                side_effect=lambda name: (
                    "/usr/bin/bwrap" if name == "bwrap" else str(executable)
                ),
            ):
                command = _sandboxed_application_command(
                    ("node", "server.mjs"), workspace,
                )

        separator = command.index("--")
        self.assertEqual(str(executable), command[separator + 1])
        self.assertEqual("server.mjs", command[separator + 2])
        bind = command.index("--ro-bind", command.index("--bind") + 1)
        toolchain = str(executable.parent.parent)
        self.assertEqual((toolchain, toolchain), command[bind + 1:bind + 3])
        path = command.index("--setenv", bind)
        self.assertEqual("PATH", command[path + 1])
        self.assertEqual(f"{executable.parent}:/usr/bin:/bin", command[path + 2])

    def test_sandbox_rejects_an_unavailable_launch_executable(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "fam_os.product.application_test_tools.shutil.which",
            side_effect=lambda name: "/usr/bin/bwrap" if name == "bwrap" else None,
        ):
            with self.assertRaisesRegex(RuntimeError, "executable is unavailable"):
                _sandboxed_application_command(("missing",), Path(directory))

    def test_runtime_availability_requires_a_real_browser_not_only_ffmpeg(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / ".cache/ms-playwright/ffmpeg-1011").mkdir(parents=True)
            with (
                patch(
                    "fam_os.product.application_test_tools.importlib.util.find_spec",
                    return_value=object(),
                ),
                patch(
                    "fam_os.product.application_test_tools.shutil.which",
                    return_value=None,
                ),
                patch(
                    "fam_os.product.application_test_tools.Path.home",
                    return_value=home,
                ),
            ):
                self.assertFalse(PlaywrightBrowserDriver.available())
                (home / ".cache/ms-playwright/chromium-1234").mkdir()
                self.assertTrue(PlaywrightBrowserDriver.available())

    def test_calculator_objective_compiles_behavior_and_diagnostic_checks(self):
        plan = ApplicationTestingObjectiveCompiler().compile(
            "Test the calculator and make sure all operations work."
        )

        self.assertEqual(
            {
                "addition", "subtraction", "multiplication", "division",
                "clear", "keyboard", "console_errors", "network_failures",
            },
            {item.check_id for item in plan.checks},
        )
        self.assertIn("browser_trace", plan.artifacts)
        self.assertIn("final_screenshot", plan.artifacts)

    def test_application_profile_exposes_session_tools_only_when_available(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = AgentToolRegistry()
            tools = ApplicationTestTools(
                Path(directory), objective="Test it", driver_factory=_UnavailableDriver,
            )
            tools.register(registry)

            self.assertFalse(registry.contains(
                "app_start", AgentAuthorityProfile.APPLICATION_TEST,
            ))
            self.assertFalse(registry.contains(
                "app_start", AgentAuthorityProfile.WORKSPACE,
            ))
            self.assertFalse(registry.contains(
                "app_click", AgentAuthorityProfile.APPLICATION_TEST,
            ))

    def test_session_owns_snapshot_actions_assertions_artifacts_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                lambda *args, **kwargs: SimpleHTTPRequestHandler(
                    *args, directory=directory, **kwargs,
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                registry = AgentToolRegistry()
                tools = ApplicationTestTools(
                    root, objective="Test calculator", driver_factory=_FakeDriver,
                )
                tools.register(registry)
                profile = AgentAuthorityProfile.APPLICATION_TEST
                self.assertTrue(registry.contains(
                    "app_start", AgentAuthorityProfile.FULL_OS,
                ))
                started = registry.invoke(AgentToolCall(
                    "start", "app_start", {
                        "application_id": "calculator",
                        "url": f"http://127.0.0.1:{server.server_port}/",
                        "checks": [{
                            "check_id": "addition",
                            "description": "Addition returns twelve.",
                            "kind": "text", "expected": "12",
                        }],
                    }, "Start the calculator test session.",
                ), profile)
                self.assertTrue(started.succeeded, started.output)
                self.assertTrue(registry.contains("app_click", profile))
                self.assertFalse(registry.contains(
                    "act_on_application", AgentAuthorityProfile.ASK,
                ))

                clicked = registry.invoke(AgentToolCall(
                    "click", "app_click", {"ref": "s1e1"}, "Calculate.",
                ), profile)
                self.assertTrue(clicked.succeeded, clicked.output)
                self.assertIn("12", json.loads(clicked.output)["document_text"])

                for call_id, check_id, kind, expected in (
                    ("assert-1", "addition", "text", "12"),
                    ("assert-2", "console_errors", "console_errors", "0"),
                    ("assert-3", "network_failures", "network_failures", "0"),
                ):
                    result = registry.invoke(AgentToolCall(
                        call_id, "app_assert", {
                            "check_id": check_id, "kind": kind,
                            "expected": expected,
                        }, "Verify the application evidence.",
                    ), profile)
                    self.assertTrue(result.succeeded, result.output)
                    self.assertTrue(result.postcondition["verified"])

                screenshot = registry.invoke(AgentToolCall(
                    "shot", "app_screenshot", {"name": "calculator-final"},
                    "Capture visual evidence.",
                ), profile)
                self.assertTrue(screenshot.postcondition["verified"])
                stopped = registry.invoke(AgentToolCall(
                    "stop", "app_stop", {}, "Finish and clean up.",
                ), profile)
                self.assertTrue(stopped.postcondition["verified"])
                self.assertFalse(registry.contains("app_click", profile))
                session_files = tuple(root.glob(
                    ".fam-test-artifacts/app-test-*/session.json"
                ))
                self.assertEqual(1, len(session_files))
                state = json.loads(session_files[0].read_text())
                self.assertEqual("completed", state["status"])
                self.assertEqual(3, len(state["assertions"]))
                self.assertEqual("calculator", state["application_id"])
                self.assertEqual("fake", state["browser_identity"]["engine"])
                self.assertIn("current_snapshot", state)
                self.assertIn("console_events", state)
                self.assertIn("network_events", state)
                self.assertEqual("stop_on_completion", state["cleanup_policy"])
                self.assertTrue(state["screenshots"])
                self.assertTrue(state["trace"])
                self.assertTrue((session_files[0].parent / "trace.zip").is_file())
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_interrupted_session_is_persisted_and_next_session_records_lineage(self):
        with tempfile.TemporaryDirectory() as directory:
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                lambda *args, **kwargs: SimpleHTTPRequestHandler(
                    *args, directory=directory, **kwargs,
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_port}/"
            try:
                first = ApplicationTestTools(
                    Path(directory), objective="Test it",
                    driver_factory=_FakeDriver,
                )
                first.start({"application_id": "app", "url": url})
                interrupted_id = first.session.session_id
                first.cleanup(interrupted=True)
                self.assertEqual("interrupted", first.session.status)

                second = ApplicationTestTools(
                    Path(directory), objective="Test it",
                    driver_factory=_FakeDriver,
                )
                resumed = json.loads(second.start({
                    "application_id": "app", "url": url,
                }))
                self.assertEqual(interrupted_id, resumed["resumed_from"])
                second.cleanup()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


class _UnavailableDriver:
    @staticmethod
    def available():
        return False


class _FakeDriver:
    def __init__(self):
        self.value = "0"
        self.generation = 0

    @staticmethod
    def available():
        return True

    def start(self, url, _artifact_root):
        self.url = url
        return {"engine": "fake", "browser": "test"}

    def snapshot(self):
        self.generation += 1
        return {
            "generation": self.generation, "url": self.url,
            "title": "Calculator", "document_text": self.value,
            "elements": [{"ref": f"s{self.generation}e1", "role": "button", "name": "="}],
        }

    def click(self, _ref):
        self.value = "12"
        return self.snapshot()

    def fill(self, _ref, value):
        self.value = value
        return self.snapshot()

    def select(self, _ref, value):
        self.value = value
        return self.snapshot()

    def press(self, key, _ref=None):
        self.value = key
        return self.snapshot()

    def screenshot(self, path):
        path.write_bytes(b"PNG")

    def console_errors(self):
        return ()

    def network_failures(self):
        return ()

    def stop(self, trace_path):
        trace_path.write_bytes(b"trace")
        return {"stopped": True}


if __name__ == "__main__":
    unittest.main()
