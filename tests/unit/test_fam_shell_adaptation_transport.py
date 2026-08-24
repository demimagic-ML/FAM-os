import os
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from fam_os.adapters.shell import (
    ShellRequestDispatcher,
    UnixShellClientConfiguration,
    UnixShellCoreClient,
    UnixShellServer,
    UnixShellServerConfiguration,
)
from fam_os.applications.transport.auth import PeerAuthorizationPolicy
from fam_os.adaptation import (
    AdaptationControlOperation,
    AdaptationControlStatus,
    LiveAdaptationControlReceipt,
    LiveAdaptationControlRequest,
)
from fam_os.schemas import decode_document, encode_document
from fam_os.shell import (
    ShellController,
    ShellAdaptationOperation,
    ShellAdaptationQuery,
    ShellAdaptationResponse,
    TerminalShell,
)
from fam_os.shell.wire import (
    ShellWireKind,
    adaptation_response_message,
    decode_adaptation_response,
    decode_request,
    request_message,
)
from tests.contract.schema_manifest_fixtures import (
    live_adaptation_control_values,
    live_adaptation_values,
)


class ShellAdaptationWireTests(unittest.TestCase):
    def test_query_response_and_control_are_strict_registered_roots(self):
        state = live_adaptation_control_values()[0]
        query = ShellAdaptationQuery(
            "status-1", ShellAdaptationOperation.STATUS, limit=1,
        )
        response = ShellAdaptationResponse(
            query.request_id, query.operation, 0, 1, state=state,
        )
        control = LiveAdaptationControlRequest(
            "disable-1", AdaptationControlOperation.DISABLE, True,
        )
        self.assertEqual(query, decode_document(encode_document(query)))
        self.assertEqual(response, decode_document(encode_document(response)))
        self.assertEqual(control, decode_document(encode_document(control)))
        message = adaptation_response_message("response-1", "request-1", response)
        self.assertEqual(response, decode_adaptation_response(message))
        self.assertEqual(
            control,
            decode_request(request_message(
                "message-1", ShellWireKind.ADAPTATION_CONTROL, control,
            )),
        )


class ShellAdaptationTransportTests(unittest.TestCase):
    def test_authenticated_endpoint_inspects_and_controls_live_adaptation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = _private_socket_path(temporary)
            adaptation = _AdaptationGateway()
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(
                    _UnusedCore(), message_id_factory=ids("response"),
                    adaptation=adaptation,
                ),
            )
            server.open()
            self.addCleanup(server.close)
            client = UnixShellCoreClient(
                UnixShellClientConfiguration(path), ids("request"),
            )
            status = ShellAdaptationQuery(
                "status-1", ShellAdaptationOperation.STATUS, limit=1,
            )
            response = serve(server, lambda: client.adaptation_query(status))
            self.assertTrue(response.state.enabled)
            snapshots = ShellAdaptationQuery(
                "snapshots-1", ShellAdaptationOperation.SNAPSHOTS,
            )
            self.assertEqual(1, serve(
                server, lambda: client.adaptation_query(snapshots),
            ).total_count)
            control = LiveAdaptationControlRequest(
                "disable-1", AdaptationControlOperation.DISABLE, True,
            )
            receipt = serve(
                server, lambda: client.adaptation_control(control),
            ).control_receipts[0]
            self.assertFalse(receipt.state.enabled)

    def test_absent_adaptation_service_returns_stable_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = _private_socket_path(temporary)
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(_UnusedCore()),
            )
            server.open()
            self.addCleanup(server.close)
            client = UnixShellCoreClient(UnixShellClientConfiguration(path))
            query = ShellAdaptationQuery(
                "status-1", ShellAdaptationOperation.STATUS, limit=1,
            )
            with self.assertRaisesRegex(RuntimeError, "shell.adaptation_unavailable"):
                serve(server, lambda: client.adaptation_query(query))

    def test_terminal_exposes_status_and_requires_confirmed_mutation(self):
        gateway = _AdaptationGateway()
        controller = ShellController(_AdaptationClient(gateway), lambda: "shell-request")
        terminal = TerminalShell(controller)

        status, _ = terminal.execute("/adaptation status")
        denied, _ = terminal.execute("/adaptation disable")
        disabled, _ = terminal.execute("/adaptation disable --confirm")

        self.assertIn("Adaptation: enabled", status)
        self.assertEqual("Command could not be completed safely.", denied)
        self.assertIn("disable | applied", disabled)


class _AdaptationGateway:
    def __init__(self):
        self.state = live_adaptation_control_values()[0]
        self.snapshot, self.prewarm = live_adaptation_values()
        self._receipts = []

    def control_state(self):
        return self.state

    def snapshots(self):
        return (self.snapshot,)

    def receipts(self):
        return (self.prewarm,)

    def health(self):
        return (live_adaptation_control_values()[4],)

    def drift_reports(self):
        return (live_adaptation_control_values()[6],)

    def control_receipts(self):
        return tuple(self._receipts)

    def apply_control(self, request):
        self.state = replace(
            self.state, revision=self.state.revision + 1, enabled=False,
            updated_at=datetime(2026, 7, 17, tzinfo=UTC),
            last_operation=request.operation,
        )
        receipt = LiveAdaptationControlReceipt(
            f"receipt-{request.request_id}", request.request_id, request.operation,
            AdaptationControlStatus.APPLIED, self.state.updated_at,
            self.state.revision - 1, self.state, request.target_workflow_id,
            0, 0, 0, ("adaptation.disabled",),
        )
        self._receipts.append(receipt)
        return receipt


class _UnusedCore:
    pass


class _AdaptationClient:
    def __init__(self, gateway):
        self.gateway = gateway

    def adaptation_query(self, command):
        from fam_os.adapters.shell.adaptation_dispatch import dispatch_adaptation
        return dispatch_adaptation(self.gateway, command)

    def adaptation_control(self, command):
        from fam_os.adapters.shell.adaptation_dispatch import dispatch_adaptation
        return dispatch_adaptation(self.gateway, command)


def _private_socket_path(directory):
    root = Path(directory)
    os.chmod(root, 0o700)
    return root / "shell.sock"


def ids(prefix):
    values = iter(range(30))
    return lambda: f"{prefix}-{next(values)}"


def serve(server, operation):
    result = []
    failure = []
    thread = threading.Thread(target=lambda: _capture(operation, result, failure))
    thread.start()
    server.serve_once()
    thread.join(timeout=5)
    if failure:
        raise failure[0]
    return result[0]


def _capture(operation, result, failure):
    try:
        result.append(operation())
    except Exception as error:
        failure.append(error)


if __name__ == "__main__":
    unittest.main()
