import json
import http.cookiejar
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from fam_os.applications import CapabilityKind
from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider
from fam_os.console.tasks import ConsoleTaskApi
from fam_os.console.workspaces import ConsoleWorkspaceApi
from fam_os.core.contracts import ResultStatus
from fam_os.core.ingress.shell_views import accepted_shell_snapshot
from fam_os.shell import ShellResult, ShellRunState, ShellSessionSnapshot
from fam_os.memory import DocumentIndexReceipt


@dataclass(frozen=True)
class _RemoteExecutionEvidence:
    evidence_id: str = "remote-evidence-1"
    request_id: str = "request-1"
    disposition: str = "released"
    verification_outcome: str = "passed"
    raw_content_retained: bool = False
    partial_output_retained: bool = False


@dataclass(frozen=True)
class _RemoteRecoveryEvidence:
    evidence_id: str = "remote-recovery-1"
    request_id: str = "request-1"
    disposition: str = "recovered"
    unchanged_acceptance: bool = True
    raw_content_retained: bool = False
    partial_output_retained: bool = False


@dataclass(frozen=True)
class _BudgetSnapshot:
    plan_instance_id: str = "task-request-1"
    consumed_tokens: int = 1024
    consumed_wall_milliseconds: int = 300_000
    repairs: int = 0
    escalations: int = 0
    reservation_ids: tuple[str, ...] = ("budget-remote-1",)


@dataclass(frozen=True)
class _BudgetReservation:
    reservation_id: str = "budget-remote-1"
    plan_instance_id: str = "task-request-1"
    attempt_id: str = "attempt-remote-1"
    kind: str = "remote"
    reserved_tokens: int = 1024
    reserved_wall_milliseconds: int = 300_000
    acceptance_sha256: str = "a" * 64
    route_plan_id: str = "remote-plan-1"


class _Reversals:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = []

    def status(self, task_id):
        self.calls.append(("status", task_id))
        return {
            "available": True, "reason_code": None,
            "source_session_id": task_id, "capability_id": "editor.undo",
            "expected_revision": 2,
        }

    def start(self, task_id, request_id, revision):
        self.calls.append(("start", task_id, request_id, revision))
        return self.snapshot


class _TaskGateway:
    def __init__(self):
        self.snapshot_value = accepted_shell_snapshot("task-request-1", "request-1")
        self.calls = []
        self.reversals = _Reversals(self.snapshot_value)

    def ask(self, command):
        self.calls.append(("ask", command))
        return self.snapshot_value

    def snapshot(self, task_id):
        self.calls.append(("snapshot", task_id))
        if task_id != self.snapshot_value.session_id:
            raise KeyError(task_id)
        return self.snapshot_value

    def decide(self, command):
        self.calls.append(("decide", command))
        return self.snapshot_value

    def cancel(self, command):
        self.calls.append(("cancel", command))
        return self.snapshot_value

    def verification_runs(self, task_id):
        self.calls.append(("verification_runs", task_id))
        return ()

    def remote_execution_evidence(self, task_id):
        self.calls.append(("remote_execution_evidence", task_id))
        if task_id != self.snapshot_value.session_id:
            raise KeyError(task_id)
        return _RemoteExecutionEvidence()

    def remote_recovery_evidence(self, task_id):
        self.calls.append(("remote_recovery_evidence", task_id))
        if task_id != self.snapshot_value.session_id:
            raise KeyError(task_id)
        return _RemoteRecoveryEvidence()

    def attempt_budget_evidence(self, task_id):
        self.calls.append(("attempt_budget_evidence", task_id))
        if task_id != self.snapshot_value.session_id:
            raise KeyError(task_id)
        return _BudgetSnapshot(), (_BudgetReservation(),)

    def application_activity(self, task_id):
        self.calls.append(("application_activity", task_id))
        if task_id != self.snapshot_value.session_id:
            raise KeyError(task_id)
        return None


class _Fallbacks:
    def status(self):
        return [{
            "mechanism": "accessibility", "configured": False, "active": False,
            "privacy_acknowledged": False, "privacy_impact": "bounded semantic tree",
            "include_text": False, "observation_capability":
            "linux.accessibility.observe_tree", "actions_requested": False,
            "actions_active": False, "action_primitives": [],
            "confirmation": "not_required", "resource_scopes": [],
            "issue_code": "disabled",
        }]


class _Applications:
    fallbacks = _Fallbacks()
    provider = SimpleNamespace(entries=lambda: (
        SimpleNamespace(
            instance_id="vscode-1", capability_id="vscode.editor.active",
            application_id="com.microsoft.vscode",
            resource_scopes=("file:///workspace/",),
            available=True,
            capability=SimpleNamespace(kind=CapabilityKind.OBSERVATION),
        ),
        SimpleNamespace(
            instance_id="vscode-1", capability_id="vscode.workspace_edit.apply",
            application_id="com.microsoft.vscode",
            resource_scopes=("file:///workspace/",),
            available=True,
            capability=SimpleNamespace(kind=CapabilityKind.ACTION),
        ),
    ))


class _MultiWorkspaceApplications:
    fallbacks = _Fallbacks()
    provider = SimpleNamespace(entries=lambda: (
        SimpleNamespace(
            instance_id="vscode-1", capability_id="vscode.editor.active",
            application_id="com.microsoft.vscode",
            resource_scopes=("file:///workspace/alpha/", "file:///workspace/beta/"),
            available=True,
            capability=SimpleNamespace(kind=CapabilityKind.OBSERVATION),
        ),
        SimpleNamespace(
            instance_id="vscode-1", capability_id="vscode.workspace_edit.apply",
            application_id="com.microsoft.vscode",
            resource_scopes=("file:///workspace/alpha/",),
            available=True,
            capability=SimpleNamespace(kind=CapabilityKind.ACTION),
        ),
        SimpleNamespace(
            instance_id="vscode-1", capability_id="vscode.unavailable",
            application_id="com.microsoft.vscode",
            resource_scopes=("file:///workspace/alpha/",),
            available=False,
            capability=SimpleNamespace(kind=CapabilityKind.OBSERVATION),
        ),
    ))


class _MemoryIndexes:
    def __init__(self):
        self.documents = []

    def create(self, document):
        self.documents.append(document)
        now = datetime(2026, 7, 17, tzinfo=UTC)
        return DocumentIndexReceipt(
            "receipt", "grant", ("document",), 1, 12, (),
            now, now + timedelta(days=1), True,
        )

    def list(self):
        return [{"grant_id": "grant"}]


class _FailingMemoryIndexes(_MemoryIndexes):
    def create(self, document):
        raise RuntimeError("embedding provider unavailable")


class ConsoleHttpTests(unittest.TestCase):
    def test_contexts_separate_observation_and_action_capabilities(self) -> None:
        context = ConsoleTaskApi(_TaskGateway(), _Applications()).contexts()[0]

        self.assertEqual(
            ["vscode.editor.active"], context["observation_capability_ids"],
        )
        self.assertEqual(
            ["vscode.workspace_edit.apply"], context["action_capability_ids"],
        )
        self.assertEqual(2, len(context["capability_ids"]))

    def test_contexts_expose_each_workspace_with_only_its_capabilities(self) -> None:
        contexts = ConsoleTaskApi(
            _TaskGateway(), _MultiWorkspaceApplications(),
        ).contexts()

        self.assertEqual(2, len(contexts))
        alpha, beta = contexts
        self.assertEqual("file:///workspace/alpha/", alpha["workspace_resource_ref"])
        self.assertEqual("com.microsoft.vscode — alpha", alpha["display_name"])
        self.assertEqual(["file:///workspace/alpha/"], alpha["resource_scopes"])
        self.assertEqual(
            ["vscode.editor.active", "vscode.workspace_edit.apply"],
            alpha["capability_ids"],
        )
        self.assertEqual("file:///workspace/beta/", beta["workspace_resource_ref"])
        self.assertEqual(["vscode.editor.active"], beta["capability_ids"])
        self.assertEqual([], beta["action_capability_ids"])
        self.assertNotEqual(alpha["context_id"], beta["context_id"])
        self.assertNotIn("file:///", alpha["context_id"])

    def test_console_port_can_be_rebound_after_a_clean_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
            )
            port = first.server_port
            first.server_close()

            restarted = ConsoleHttpServer(
                ("127.0.0.1", port), LocalConsoleProvider(Path(directory)), "x" * 32,
            )
            restarted.server_close()

    def test_task_api_requires_exact_confirmation_for_remote_authority(self):
        gateway = _TaskGateway()
        api = ConsoleTaskApi(gateway)
        authority = {
            "enrollment_id": "enrollment-1",
            "expected_privacy_revision": 2,
            "purpose_id": "assist",
            "workspace_id": "workspace:test",
            "sensitivity": "private",
            "maximum_context_bytes": 8192,
            "maximum_output_bytes": 4096,
            "confirmed": False,
        }
        with self.assertRaisesRegex(PermissionError, "explicitly confirmed"):
            api.create({"prompt": "Use the peer", "remote_authority": authority})
        authority["confirmed"] = True
        api.create({
            "request_id": "request-1", "prompt": "Use the peer",
            "remote_authority": authority,
        })
        command = gateway.calls[-1][1]
        self.assertEqual("enrollment-1", command.remote_authority.enrollment_id)
        self.assertEqual(2, command.remote_authority.expected_privacy_revision)

    def test_memory_indexing_requires_authenticated_csrf_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = _MemoryIndexes()
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
                ConsoleTaskApi(_TaskGateway()), memory,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                )
                exchange = urllib.request.Request(
                    base + "/api/v1/session", data=b"{}", method="POST",
                    headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
                )
                session = json.loads(opener.open(exchange).read())
                body = json.dumps({
                    "path": "/home/user/project", "kind": "folder",
                    "confirmed": True,
                }).encode()
                request = urllib.request.Request(
                    base + "/api/v1/memory/indexes", data=body, method="POST",
                    headers={
                        "Content-Type": "application/json", "Origin": base,
                        "X-CSRF-Token": session["csrf_token"],
                    },
                )
                receipt = json.loads(opener.open(request).read())
                self.assertTrue(receipt["passed"])
                self.assertEqual([json.loads(body)], memory.documents)
                listed = json.loads(opener.open(base + "/api/v1/memory/indexes").read())
                self.assertEqual("grant", listed["indexes"][0]["grant_id"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_unexpected_post_failure_is_logged_without_exposing_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
                ConsoleTaskApi(_TaskGateway()), _FailingMemoryIndexes(),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                )
                exchange = urllib.request.Request(
                    base + "/api/v1/session", data=b"{}", method="POST",
                    headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
                )
                session = json.loads(opener.open(exchange).read())
                request = urllib.request.Request(
                    base + "/api/v1/memory/indexes",
                    data=json.dumps({
                        "path": "/home/user/project", "kind": "folder",
                        "confirmed": True,
                    }).encode(),
                    method="POST",
                    headers={
                        "Content-Type": "application/json", "Origin": base,
                        "X-CSRF-Token": session["csrf_token"],
                    },
                )
                with self.assertLogs("fam_os.console.http", level="ERROR") as logs:
                    with self.assertRaises(urllib.error.HTTPError) as failure:
                        opener.open(request)
                self.assertEqual(409, failure.exception.code)
                body = json.loads(failure.exception.read())
                self.assertEqual(
                    "The task state changed or became unavailable.", body["error"],
                )
                self.assertNotIn("embedding provider unavailable", str(body))
                self.assertIn(
                    "FAM Console POST failed for /api/v1/memory/indexes",
                    "\n".join(logs.output),
                )
                self.assertIn("embedding provider unavailable", "\n".join(logs.output))
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_authenticated_loopback_snapshot_and_static_ui(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory), "v1"), "x" * 32,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                page = urllib.request.urlopen(base).read()
                self.assertIn(b"Work with your machine", page)
                self.assertIn(b"Task scope", page)
                self.assertIn(b"turn-template", page)
                self.assertIn(b"Application fabric", page)
                self.assertIn(b"Exact citations", page)
                self.assertIn(b"Memory ledger", page)
                self.assertIn(b"Open folder", page)
                self.assertIn(b"Tool terminal", page)
                application = urllib.request.urlopen(base + "/app.js").read()
                self.assertIn(b"citation.source_locator", application)
                self.assertIn(b"citation.quoted_text", application)
                self.assertIn(b"Task update interrupted / retrying", application)
                self.assertIn(b"pollFailures", application)
                self.assertIn(b"FamTaskUpdates.accepts", application)
                self.assertIn(b"FamConversation.revealText", application)
                self.assertIn(b"scrollToTurn(turn, reducedMotion)", application)
                self.assertIn(b"selected?.workspace_resource_ref", application)
                self.assertIn(b'kind: "uri"', application)
                self.assertIn(
                    b"capability_ids: selected.capability_ids", application,
                )
                self.assertNotIn(
                    b"capability_ids: selected.observation_capability_ids ||",
                    application,
                )
                self.assertIn(b"Console session expired / reopen from launcher", application)
                self.assertIn(b"error.status === 401", application)
                task_updates = urllib.request.urlopen(
                    base + "/task_updates.js",
                ).read()
                self.assertIn(b'current.state === "terminal"', task_updates)
                self.assertIn(b"next.revision < current.revision", task_updates)
                conversation = urllib.request.urlopen(
                    base + "/conversation.js",
                ).read()
                self.assertIn(b"typingDuration", conversation)
                self.assertIn(b"scrollMessageStart", conversation)
                workspace = urllib.request.urlopen(base + "/workspace.js").read()
                self.assertIn(b"Waiting for deterministic tool evidence", workspace)
                self.assertIn(b"/api/v1/workspace", workspace)
                self.assertIn(b"selectedPath", workspace)
                natural = urllib.request.urlopen(
                    base + "/natural_engineering.js",
                ).read()
                self.assertIn(b"changeset-decision", natural)
                self.assertIn(b"workspace_root", natural)
                workspace_style = urllib.request.urlopen(base + "/workspace.css")
                self.assertEqual("text/css", workspace_style.headers.get_content_type())
                memory_ui = urllib.request.urlopen(base + "/memory.js").read()
                self.assertIn(b"replacement_content_sha256", memory_ui)
                self.assertIn(b"Expire grant", memory_ui)
                memory_style = urllib.request.urlopen(base + "/memory.css")
                self.assertEqual("text/css", memory_style.headers.get_content_type())
                font = urllib.request.urlopen(
                    base + "/fonts/NotoSans-Regular.ttf",
                )
                self.assertEqual("font/ttf", font.headers.get_content_type())
                self.assertEqual(b"\x00\x01\x00\x00", font.read(4))
                with self.assertRaises(urllib.error.HTTPError) as missing_font:
                    urllib.request.urlopen(base + "/fonts/not-bundled.ttf")
                self.assertEqual(404, missing_font.exception.code)
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(base + "/api/v1/snapshot")
                self.assertEqual(denied.exception.code, 401)
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
                )
                exchange = urllib.request.Request(
                    base + "/api/v1/session", data=b"{}", method="POST",
                    headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
                )
                session = json.loads(opener.open(exchange).read())
                self.assertTrue(session["csrf_token"])
                payload = json.loads(opener.open(base + "/api/v1/snapshot").read())
                self.assertEqual(len(payload["sections"]), 6)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_task_mutations_require_session_origin_and_csrf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            gateway = _TaskGateway()
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
                ConsoleTaskApi(gateway, _Applications()),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
                )
                exchange = urllib.request.Request(
                    base + "/api/v1/session", data=b"{}", method="POST",
                    headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
                )
                session = json.loads(opener.open(exchange).read())
                body = json.dumps({
                    "request_id": "request-1", "prompt": "Explain this project",
                    "memory_session_id": "client-cannot-select-this",
                }).encode()
                denied = urllib.request.Request(
                    base + "/api/v1/tasks", data=body, method="POST",
                    headers={"Content-Type": "application/json", "Origin": base},
                )
                with self.assertRaises(urllib.error.HTTPError) as failure:
                    opener.open(denied)
                self.assertEqual(failure.exception.code, 403)
                created = urllib.request.Request(
                    base + "/api/v1/tasks", data=body, method="POST",
                    headers={
                        "Content-Type": "application/json", "Origin": base,
                        "X-CSRF-Token": session["csrf_token"],
                    },
                )
                document = json.loads(opener.open(created).read())
                self.assertEqual(document["session_id"], "task-request-1")
                ask = next(call[1] for call in gateway.calls if call[0] == "ask")
                self.assertTrue(ask.memory_session_id)
                self.assertNotEqual("client-cannot-select-this", ask.memory_session_id)
                loaded = json.loads(opener.open(
                    base + "/api/v1/tasks/task-request-1"
                ).read())
                self.assertEqual(loaded["request_id"], "request-1")
                integrations = json.loads(opener.open(
                    base + "/api/v1/integrations"
                ).read())
                self.assertEqual(
                    "disabled", integrations["integrations"][0]["issue_code"],
                )
                reversal = json.loads(opener.open(
                    base + "/api/v1/tasks/task-request-1/reversal"
                ).read())
                self.assertTrue(reversal["available"])
                verification = json.loads(opener.open(
                    base + "/api/v1/tasks/task-request-1/verification"
                ).read())
                self.assertEqual([], verification["runs"])
                remote = json.loads(opener.open(
                    base + "/api/v1/tasks/task-request-1/remote-execution"
                ).read())
                self.assertTrue(remote["available"])
                self.assertEqual(
                    "remote-evidence-1", remote["evidence"]["evidence_id"],
                )
                self.assertFalse(remote["evidence"]["raw_content_retained"])
                self.assertFalse(remote["evidence"]["partial_output_retained"])
                recovery = json.loads(opener.open(
                    base + "/api/v1/tasks/task-request-1/remote-recovery"
                ).read())
                self.assertTrue(recovery["available"])
                self.assertEqual(
                    "remote-recovery-1", recovery["evidence"]["evidence_id"],
                )
                self.assertTrue(recovery["evidence"]["unchanged_acceptance"])
                budget = json.loads(opener.open(
                    base + "/api/v1/tasks/task-request-1/budget"
                ).read())
                self.assertEqual(1024, budget["snapshot"]["consumed_tokens"])
                self.assertEqual("remote", budget["reservations"][0]["kind"])
                self.assertEqual(
                    "a" * 64,
                    budget["reservations"][0]["acceptance_sha256"],
                )
                activity = json.loads(opener.open(
                    base + "/api/v1/tasks/task-request-1/activity"
                ).read())
                self.assertFalse(activity["available"])
                undo = urllib.request.Request(
                    base + "/api/v1/tasks/task-request-1/undo",
                    data=json.dumps({
                        "request_id": "undo-1", "expected_revision": 2,
                    }).encode(),
                    method="POST",
                    headers={
                        "Content-Type": "application/json", "Origin": base,
                        "X-CSRF-Token": session["csrf_token"],
                    },
                )
                json.loads(opener.open(undo).read())
                self.assertEqual(
                    ("start", "task-request-1", "undo-1", 2),
                    gateway.reversals.calls[-1],
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_authenticated_workspace_browser_is_owner_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            (project / "src").mkdir()
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(root), "x" * 32,
                ConsoleTaskApi(_TaskGateway()),
                workspace_api=ConsoleWorkspaceApi(root),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                opener = _authenticated_opener(base)
                document = json.loads(opener.open(
                    base + "/api/v1/workspace?path="
                    + urllib.parse.quote(str(project), safe=""),
                ).read())
                self.assertEqual(str(project), document["path"])
                self.assertEqual("src", document["entries"][0]["name"])
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    opener.open(
                        base + "/api/v1/workspace?path="
                        + urllib.parse.quote("/tmp", safe=""),
                    )
                self.assertEqual(403, denied.exception.code)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_terminal_sse_replay_and_resume_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            gateway = _TaskGateway()
            gateway.snapshot_value = ShellSessionSnapshot(
                "task-request-1", "request-1", 3, ShellRunState.TERMINAL,
                result=ShellResult(
                    "request-1", ResultStatus.VERIFIED, "Verified result",
                    verified=True, evidence_ids=("evidence-1",),
                ),
            )
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
                ConsoleTaskApi(gateway),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                opener = _authenticated_opener(base)
                payload = opener.open(
                    base + "/api/v1/tasks/task-request-1/events",
                ).read()
                self.assertIn(b"id: 3\nevent: task\n", payload)
                self.assertIn(b'"state":"terminal"', payload)

                resumed = urllib.request.Request(
                    base + "/api/v1/tasks/task-request-1/events",
                    headers={"Last-Event-ID": "3"},
                )
                self.assertEqual(b"", opener.open(resumed).read())
                for event_id, expected in (("not-an-int", 400), ("-2", 400), ("4", 409)):
                    request = urllib.request.Request(
                        base + "/api/v1/tasks/task-request-1/events",
                        headers={"Last-Event-ID": event_id},
                    )
                    with self.assertRaises(urllib.error.HTTPError) as failure:
                        opener.open(request)
                    self.assertEqual(expected, failure.exception.code)
                with self.assertRaises(urllib.error.HTTPError) as missing:
                    opener.open(base + "/api/v1/tasks/missing/events")
                self.assertEqual(404, missing.exception.code)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_non_loopback_binding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "loopback"):
                ConsoleHttpServer(
                    ("0.0.0.0", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
                )


def _authenticated_opener(base):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    exchange = urllib.request.Request(
        base + "/api/v1/session", data=b"{}", method="POST",
        headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
    )
    opener.open(exchange).read()
    return opener


if __name__ == "__main__":
    unittest.main()
