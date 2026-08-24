import base64
import hashlib
import os
import tempfile
import threading
import unittest
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
from fam_os.fabric import (
    PeerManagementOperation,
    PeerManagementReceipt,
    PeerManagementRequest,
    RemoteContextDirection,
    RemoteContextDisclosureEvidence,
    RemoteContextReceipt,
    RemoteContextReceiptStatus,
    RemoteContextSendRequest,
    RemoteContextSensitivity,
    RemoteTaskDescriptor,
)
from fam_os.schemas import decode_document, dumps_document, encode_document
from fam_os.shell import (
    ShellController,
    ShellPeerOperation,
    ShellPeerProbeRequest,
    ShellPeerQuery,
    ShellPeerResponse,
    TerminalShell,
)
from fam_os.shell.wire import (
    ShellWireKind, decode_peer_response, decode_request,
    peer_response_message, request_message,
)
from tests.contract.schema_manifest_fixtures import device_identity_values

NOW = datetime(2026, 7, 17, tzinfo=UTC)


class ShellPeerWireTests(unittest.TestCase):
    def test_query_probe_control_and_response_are_registered_roots(self):
        entry = device_identity_values()[-1]
        query = ShellPeerQuery("peers-1", ShellPeerOperation.PEERS)
        probe = ShellPeerProbeRequest("probe-1", entry.enrollment_id)
        response = ShellPeerResponse(
            query.request_id, query.operation, 0, 1, peers=(entry,),
        )
        control = PeerManagementRequest(
            "revoke-1", "owner", PeerManagementOperation.REVOKE,
            entry.enrollment_id, 1, True, "owner.revoked",
        )
        context = _context_request("context-1", entry.enrollment_id)
        for value in (query, probe, response, control, context):
            self.assertEqual(value, decode_document(encode_document(value)))
        self.assertEqual(response, decode_peer_response(
            peer_response_message("response", "request", response),
        ))
        self.assertEqual(control, decode_request(request_message(
            "message", ShellWireKind.PEER_CONTROL, control,
        )))
        self.assertEqual(context, decode_request(request_message(
            "context-message", ShellWireKind.PEER_CONTEXT, context,
        )))


class ShellPeerTransportTests(unittest.TestCase):
    def test_authenticated_endpoint_lists_probes_and_controls_trusted_peers(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = _private_socket_path(temporary)
            peer = _PeerGateway()
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(
                    _UnusedCore(), message_id_factory=ids("response"), peer=peer,
                ),
            )
            server.open()
            self.addCleanup(server.close)
            client = UnixShellCoreClient(UnixShellClientConfiguration(path), ids("request"))
            query = ShellPeerQuery("peers-1", ShellPeerOperation.PEERS)
            self.assertEqual(1, serve(server, lambda: client.peer_query(query)).total_count)
            probe = ShellPeerProbeRequest("probe-1", peer.entry.enrollment_id)
            self.assertEqual(1, len(serve(server, lambda: client.peer_probe(probe)).peers))
            context = _context_request("context-1", peer.entry.enrollment_id)
            disclosed = serve(server, lambda: client.peer_context(context))
            self.assertEqual(1, len(disclosed.context_evidence))
            control = PeerManagementRequest(
                "revoke-1", "owner", PeerManagementOperation.REVOKE,
                peer.entry.enrollment_id, 1, True, "owner.revoked",
            )
            receipt = serve(server, lambda: client.peer_control(control)).control_receipts[0]
            self.assertTrue(receipt.applied)

    def test_absent_peer_service_returns_stable_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = _private_socket_path(temporary)
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()), ShellRequestDispatcher(_UnusedCore()),
            )
            server.open()
            self.addCleanup(server.close)
            client = UnixShellCoreClient(UnixShellClientConfiguration(path))
            with self.assertRaisesRegex(RuntimeError, "shell.peer_unavailable"):
                serve(server, lambda: client.peer_query(
                    ShellPeerQuery("peers-1", ShellPeerOperation.PEERS),
                ))

    def test_terminal_lists_and_requires_literal_revoke_confirmation(self):
        gateway = _PeerGateway()
        controller = ShellController(
            _PeerClient(gateway), lambda: "shell-request", owner_id="owner",
        )
        terminal = TerminalShell(controller)
        listed, _ = terminal.execute("/peer list")
        context, _ = terminal.execute(
            f"/peer context {gateway.entry.enrollment_id} expert.code capability-1 "
            "1 assist workspace:test private intent.code code.generate verified 4096"
        )
        denied, _ = terminal.execute(
            f"/peer revoke {gateway.entry.enrollment_id} 1 owner.revoked",
        )
        revoked, _ = terminal.execute(
            f"/peer revoke {gateway.entry.enrollment_id} 1 owner.revoked --confirm",
        )
        self.assertIn("trusted=true", listed)
        self.assertIn("context.receipt_verified", context)
        self.assertEqual("Command could not be completed safely.", denied)
        self.assertIn("revoke | applied=true", revoked)


class _PeerGateway:
    def __init__(self):
        self.entry = device_identity_values()[-1]
        self._receipts = []
        self._context = []

    def trusted_peers(self):
        return () if self._receipts else (self.entry,)

    def peer(self, enrollment_id):
        if enrollment_id != self.entry.enrollment_id:
            raise KeyError(enrollment_id)
        return self.entry

    def probe(self, enrollment_id, request_id=None):
        return self.peer(enrollment_id)

    def control_receipts(self):
        return tuple(self._receipts)

    def apply_control(self, request):
        if not request.confirmed:
            raise PermissionError("confirmation required")
        digest = hashlib.sha256(dumps_document(request).encode()).hexdigest()
        receipt = PeerManagementReceipt(
            "receipt-" + request.request_id, request.request_id, request.owner_id,
            request.operation, request.enrollment_id, digest,
            request.expected_revision, request.expected_revision + 1, True,
            (request.reason_code,), NOW,
        )
        self._receipts.append(receipt)
        return receipt

    def send_context(self, request):
        evidence = _context_evidence(request, self.entry)
        self._context.append(evidence)
        return evidence

    def context_evidence(self):
        return tuple(self._context)


class _PeerClient:
    def __init__(self, gateway):
        self.gateway = gateway

    def peer_query(self, command):
        from fam_os.adapters.shell.peer_dispatch import dispatch_peer
        return dispatch_peer(self.gateway, command)

    def peer_probe(self, command):
        from fam_os.adapters.shell.peer_dispatch import dispatch_peer
        return dispatch_peer(self.gateway, command)

    def peer_control(self, command):
        from fam_os.adapters.shell.peer_dispatch import dispatch_peer
        return dispatch_peer(self.gateway, command)

    def peer_context(self, command):
        from fam_os.adapters.shell.peer_dispatch import dispatch_peer
        return dispatch_peer(self.gateway, command)


class _UnusedCore:
    pass


def _context_request(request_id, enrollment_id):
    return RemoteContextSendRequest(
        request_id, enrollment_id, "expert.code", "capability-1", 1,
        "assist", "workspace:test", RemoteContextSensitivity.PRIVATE,
        RemoteTaskDescriptor(
            "intent.code", ("code.generate",), "verified", 4096,
        ),
    )


def _context_evidence(request, entry):
    content_sha256 = "b" * 64
    receipt = RemoteContextReceipt(
        "context-receipt-1", request.request_id, "context-1", "sender-device",
        entry.device_id, RemoteContextReceiptStatus.ACCEPTED, 128,
        content_sha256, 0, NOW, base64.b64encode(bytes(64)).decode(),
    )
    return RemoteContextDisclosureEvidence(
        "context-evidence-1", request.request_id,
        hashlib.sha256(dumps_document(request).encode()).hexdigest(),
        request.enrollment_id, entry.device_id, RemoteContextDirection.OUTBOUND,
        "context-1", request.target_expert_id, request.purpose_id,
        request.workspace_id, request.sensitivity, 128, content_sha256, (), 1,
        request.capability_declaration_id, receipt,
        ("privacy.approved", "context.receipt_verified"), NOW,
    )


def _private_socket_path(directory):
    root = Path(directory)
    os.chmod(root, 0o700)
    return root / "shell.sock"


def ids(prefix):
    values = iter(range(30))
    return lambda: f"{prefix}-{next(values)}"


def serve(server, operation):
    result, failure = [], []
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
