import os
import http.cookiejar
import json
import socket
import tempfile
import threading
import time
import unittest
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.shell import UnixShellClientConfiguration, UnixShellCoreClient
from fam_os.applications import (
    ApplicationAuthority,
    ApplicationFailure,
    ApplicationFailureCategory,
    ApplicationRetryDisposition,
    ApplicationIdentity,
    ApplicationInstance,
    CapabilityDescriptor,
    CapabilityKind,
    CapabilityRegistryEntry,
    ConfirmationPolicy,
    ConnectorRegistration,
    ConnectorTransportKind,
    ObservationResult,
    ObservationStatus,
    Reversibility,
)
from fam_os.applications.transport import (
    LocalMessageKind,
    contract_message,
    decode_contract_message,
    receive_frame,
    send_frame,
)
from fam_os.core.contracts import ResultAssurance, ResultStatus
from fam_os.core.ports import InferenceResponse
from fam_os.product.service import LocalProductService, ProductServiceSettings
from fam_os.shell import ShellAskCommand, ShellContext, ShellContextKind
from fam_os.telemetry import InferenceMetrics
from tests.integration.product_runtime_fixture import (
    ContextProfileFixture,
    ResidentRuntimeFixture,
)


class _Runtime(ResidentRuntimeFixture):
    def __init__(self):
        super().__init__()

    def chat(self, request):
        self.request = request
        return InferenceResponse(
            "The active editor contains the observed FAM_OS project file.",
            InferenceMetrics(request.model_ref, 0.01, 0.0, 8, 4, 400.0),
        )

class ProductApplicationFabricTests(unittest.TestCase):
    def test_live_connector_resolves_active_editor_inside_registered_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = LocalProductService(ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            ), _Runtime(), context_profile_observer=ContextProfileFixture())
            service.start()
            connector = _Connector(root / "runtime/applications.sock")
            connector.start()
            try:
                self.assertTrue(connector.registered.wait(2))
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                accepted = client.ask(ShellAskCommand(
                    "active-editor-request", "Summarize the active editor.",
                    (ShellContext(
                        "application", ShellContextKind.APPLICATION,
                        "instance-live", "Visual Studio Code",
                        ("vscode.editor.active",),
                    ),),
                ))

                result = _terminal(client, accepted.session_id)

                self.assertEqual(ResultAssurance.GROUNDED, result.result.assurance)
                self.assertTrue(connector.observed.wait(1))
                self.assertIsNone(connector.last_request.resource_uri)
            finally:
                connector.close()
                service.stop()

    def test_live_connector_observation_grounds_installed_shell_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = LocalProductService(ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            ), _Runtime(), context_profile_observer=ContextProfileFixture())
            service.start()
            connector = _Connector(root / "runtime/applications.sock")
            connector.start()
            try:
                self.assertTrue(connector.registered.wait(2))
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                accepted = client.ask(ShellAskCommand(
                    "application-request", "Summarize the active project file.",
                    (
                        ShellContext(
                            "application", ShellContextKind.APPLICATION,
                            "instance-live", "Visual Studio Code",
                            ("vscode.editor.active",),
                        ),
                        ShellContext(
                            "resource", ShellContextKind.FILE,
                            "file:///workspace/main.py", "main.py",
                        ),
                    ),
                ))
                result = _terminal(client, accepted.session_id)
                self.assertEqual(ResultAssurance.GROUNDED, result.result.assurance)
                self.assertIn("observed FAM_OS", result.result.content)
                self.assertTrue(connector.observed.wait(1))
            finally:
                connector.close()
                service.stop()

    def test_connector_scope_rejection_reaches_a_terminal_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = LocalProductService(ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            ), _Runtime(), context_profile_observer=ContextProfileFixture())
            service.start()
            connector = _Connector(root / "runtime/applications.sock")
            connector.start()
            try:
                self.assertTrue(connector.registered.wait(2))
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                accepted = client.ask(ShellAskCommand(
                    "outside-scope-request", "Summarize the other project file.",
                    (
                        ShellContext(
                            "application", ShellContextKind.APPLICATION,
                            "instance-live", "Visual Studio Code",
                            ("vscode.editor.active",),
                        ),
                        ShellContext(
                            "resource", ShellContextKind.FILE,
                            "file:///other-project/main.py", "main.py",
                        ),
                    ),
                ))
                result = _terminal(client, accepted.session_id)
                self.assertEqual(ResultStatus.FAILED, result.result.status)
                self.assertFalse(result.result.content)
                self.assertFalse(connector.observed.is_set())
            finally:
                connector.close()
                service.stop()

    def test_connector_failure_reaches_a_terminal_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = LocalProductService(ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            ), _Runtime(), context_profile_observer=ContextProfileFixture())
            service.start()
            connector = _Connector(
                root / "runtime/applications.sock", fail_observations=True,
            )
            connector.start()
            try:
                self.assertTrue(connector.registered.wait(2))
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                accepted = client.ask(ShellAskCommand(
                    "failed-connector-request", "Summarize the active project file.",
                    (
                        ShellContext(
                            "application", ShellContextKind.APPLICATION,
                            "instance-live", "Visual Studio Code",
                            ("vscode.editor.active",),
                        ),
                        ShellContext(
                            "resource", ShellContextKind.FILE,
                            "file:///workspace/main.py", "main.py",
                        ),
                    ),
                ))
                result = _terminal(client, accepted.session_id)
                self.assertEqual(ResultStatus.FAILED, result.result.status)
                self.assertFalse(result.result.content)
            finally:
                connector.close()
                service.stop()

    def test_connector_timeout_reaches_a_terminal_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = LocalProductService(ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            ), _Runtime(), context_profile_observer=ContextProfileFixture())
            service.start()
            service.application_fabric.broker.timeout_seconds = 0.05
            connector = _Connector(
                root / "runtime/applications.sock", hang_observations=True,
            )
            connector.start()
            try:
                self.assertTrue(connector.registered.wait(2))
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                accepted = client.ask(ShellAskCommand(
                    "timed-out-connector-request",
                    "Summarize the active project file.",
                    (
                        ShellContext(
                            "application", ShellContextKind.APPLICATION,
                            "instance-live", "Visual Studio Code",
                            ("vscode.editor.active",),
                        ),
                        ShellContext(
                            "resource", ShellContextKind.FILE,
                            "file:///workspace/main.py", "main.py",
                        ),
                    ),
                ))
                result = _terminal(client, accepted.session_id)
                self.assertEqual(ResultStatus.FAILED, result.result.status)
                self.assertFalse(result.result.content)
            finally:
                connector.close()
                service.stop()

    def test_failed_observation_evidence_reaches_a_terminal_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = LocalProductService(ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            ), _Runtime(), context_profile_observer=ContextProfileFixture())
            service.start()
            connector = _Connector(
                root / "runtime/applications.sock", return_failed_observation=True,
            )
            connector.start()
            try:
                self.assertTrue(connector.registered.wait(2))
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                accepted = client.ask(ShellAskCommand(
                    "failed-observation-request",
                    "Summarize the active project file.",
                    (
                        ShellContext(
                            "application", ShellContextKind.APPLICATION,
                            "instance-live", "Visual Studio Code",
                            ("vscode.editor.active",),
                        ),
                        ShellContext(
                            "resource", ShellContextKind.FILE,
                            "file:///workspace/main.py", "main.py",
                        ),
                    ),
                ))
                result = _terminal(client, accepted.session_id)
                self.assertEqual(ResultStatus.FAILED, result.result.status)
                self.assertFalse(result.result.content)
            finally:
                connector.close()
                service.stop()

    def test_failed_observation_closes_console_event_stream_with_terminal_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = LocalProductService(ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            ), _Runtime(), context_profile_observer=ContextProfileFixture())
            service.start()
            connector = _Connector(
                root / "runtime/applications.sock", return_failed_observation=True,
            )
            connector.start()
            try:
                self.assertTrue(connector.registered.wait(2))
                base = f"http://127.0.0.1:{service.console_server.server_port}"
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                )
                token = (root / "runtime/console.token").read_text().strip()
                session_request = urllib.request.Request(
                    base + "/api/v1/session", data=b"{}", method="POST",
                    headers={"Authorization": f"Bearer {token}", "Origin": base},
                )
                session = json.load(opener.open(session_request, timeout=2))
                body = json.dumps({
                    "request_id": "failed-observation-console-request",
                    "prompt": "Summarize the active project file.",
                    "contexts": [{
                        "context_id": "application",
                        "kind": "application",
                        "resource_ref": "instance-live",
                        "display_name": "Visual Studio Code",
                        "capability_ids": ["vscode.editor.active"],
                    }],
                }).encode()
                create_request = urllib.request.Request(
                    base + "/api/v1/tasks", data=body, method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-CSRF-Token": session["csrf_token"],
                        "Origin": base,
                    },
                )
                accepted = json.load(opener.open(create_request, timeout=2))

                started = time.monotonic()
                event_stream = opener.open(
                    base + f"/api/v1/tasks/{accepted['session_id']}/events",
                    timeout=2,
                ).read()

                self.assertLess(time.monotonic() - started, 2)
                self.assertIn(b'"state":"terminal"', event_stream)
                self.assertIn(b'"status":"failed"', event_stream)
                self.assertIn(b'"result":{', event_stream)
            finally:
                connector.close()
                service.stop()


class _Connector:
    def __init__(
        self, path, *, fail_observations=False, hang_observations=False,
        return_failed_observation=False,
    ):
        self.path = path
        self.fail_observations = fail_observations
        self.hang_observations = hang_observations
        self.return_failed_observation = return_failed_observation
        self.registered = threading.Event()
        self.observed = threading.Event()
        self.last_request = None
        self._stream = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def close(self):
        if self._stream is not None:
            try:
                self._stream.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._stream.close()
        self._thread.join(timeout=2)

    def _run(self):
        stream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._stream = stream
        stream.connect(str(self.path))
        send_frame(stream, contract_message(
            "register-live", LocalMessageKind.REGISTER, _registration(),
        ))
        receive_frame(stream)
        self.registered.set()
        try:
            while True:
                message = receive_frame(stream)
                if message.kind is not LocalMessageKind.OBSERVE:
                    continue
                if self.fail_observations:
                    stream.shutdown(socket.SHUT_RDWR)
                    stream.close()
                    return
                if self.hang_observations:
                    continue
                request = decode_contract_message(message)
                self.last_request = request
                if self.return_failed_observation:
                    result = ObservationResult(
                        request.request_id, ObservationStatus.FAILED,
                        datetime.now(timezone.utc),
                        error=ApplicationFailure(
                            ApplicationFailureCategory.EXECUTION_FAILED,
                            "application.connector.failed",
                            "The connector could not observe the editor.",
                            ApplicationRetryDisposition.WITH_BACKOFF,
                        ),
                    )
                    send_frame(stream, contract_message(
                        "observation-failed", LocalMessageKind.OBSERVATION,
                        result, message.message_id,
                    ))
                    continue
                observed_uri = request.resource_uri or "file:///workspace/main.py"
                result = ObservationResult(
                    request.request_id, ObservationStatus.OBSERVED,
                    datetime.now(timezone.utc),
                    {"document_uri": observed_uri, "language_id": "python"},
                    observed_uri, "vscode-document:1:" + "a" * 64,
                )
                send_frame(stream, contract_message(
                    "observation-live", LocalMessageKind.OBSERVATION,
                    result, message.message_id,
                ))
                self.observed.set()
        except (EOFError, OSError):
            pass


def _registration():
    application = ApplicationIdentity("com.microsoft.vscode", "Visual Studio Code")
    instance = ApplicationInstance(
        "instance-live", application, "connector-live", os.getpid(),
        ("file:///workspace/",),
    )
    capability = CapabilityDescriptor(
        "vscode.editor.active", "Observe active editor", "Semantic editor state.",
        CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
        "vscode.editor.active.input.v1", "vscode.editor.active.output.v1",
        Reversibility.NOT_APPLICABLE, ConfirmationPolicy.NOT_REQUIRED,
    )
    entry = CapabilityRegistryEntry(
        "entry-live", "connector-live", "instance-live",
        application.application_id, capability, ("file:///workspace/",),
    )
    return ConnectorRegistration(
        "connector-live", ConnectorTransportKind.NATIVE_LOCAL,
        "fam.native-connector", "1", instance, (entry,),
        datetime.now(timezone.utc),
    )


def _terminal(client, session_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        snapshot = client.snapshot(session_id)
        if snapshot.result is not None:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("application task did not become terminal")


if __name__ == "__main__":
    unittest.main()
