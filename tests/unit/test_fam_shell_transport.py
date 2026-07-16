import os
import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path

from fam_os.adapters.shell import (
    ShellRequestDispatcher,
    UnixShellClientConfiguration,
    UnixShellCoreClient,
    UnixShellServer,
    UnixShellServerConfiguration,
)
from fam_os.applications.transport.auth import PeerAuthorizationPolicy
from fam_os.core.contracts import ResultStatus
from fam_os.schemas import decode_document, encode_document
from fam_os.shell import (
    ShellAskCommand,
    ShellCancelCommand,
    ShellDecision,
    ShellDecisionCommand,
    ShellResult,
    ShellRunState,
    ShellSessionSnapshot,
    ShellSnapshotQuery,
)
from fam_os.shell.wire import (
    ShellWireKind,
    ShellWireMessage,
    decode_request,
    encode_frame,
    message_document,
    message_from_document,
    receive_frame,
    request_message,
)


class ShellWireTests(unittest.TestCase):
    def test_registered_shell_documents_round_trip_strictly(self):
        values = (
            ShellAskCommand("request-1", "Help"),
            ShellSnapshotQuery("session-1"),
            ShellDecisionCommand("session-1", 1, "approval-1", ShellDecision.APPROVE),
            ShellCancelCommand("session-1", 1),
            accepted(),
        )
        for value in values:
            self.assertEqual(value, decode_document(encode_document(value)))

    def test_wire_rejects_wrong_schema_extra_fields_and_oversize(self):
        wrong = ShellWireMessage(
            "message-1", ShellWireKind.ASK, encode_document(accepted())
        )
        with self.assertRaisesRegex(ValueError, "schema does not match"):
            decode_request(wrong)
        document = message_document(request_message(
            "message-2", ShellWireKind.ASK, ShellAskCommand("request-1", "Help")
        ))
        document["extra"] = True
        with self.assertRaises(ValueError):
            message_from_document(document)
        left, right = socket.socketpair()
        try:
            left.sendall(struct.pack("!I", 2_000_000))
            with self.assertRaisesRegex(ValueError, "size"):
                receive_frame(right)
        finally:
            left.close()
            right.close()

    def test_frame_is_deterministic_and_bounded(self):
        message = request_message(
            "message-1", ShellWireKind.ASK, ShellAskCommand("request-1", "Help")
        )
        self.assertEqual(encode_frame(message), encode_frame(message))
        with self.assertRaisesRegex(ValueError, "limit"):
            encode_frame(message, maximum=10)


class UnixShellTransportTests(unittest.TestCase):
    def test_authenticated_endpoint_carries_all_client_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            path = root / "shell.sock"
            gateway = Gateway()
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(gateway, message_id_factory=ids("response")),
            )
            server.open()
            self.addCleanup(server.close)
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
            client = UnixShellCoreClient(
                UnixShellClientConfiguration(path), ids("request")
            )

            self.assertEqual(ShellRunState.ACCEPTED, serve(server, lambda: client.ask(
                ShellAskCommand("request-1", "Help")
            )).state)
            self.assertEqual(ShellRunState.RUNNING, serve(
                server, lambda: client.snapshot("session-1")
            ).state)
            self.assertEqual(ShellRunState.RUNNING, serve(server, lambda: client.decide(
                ShellDecisionCommand(
                    "session-1", 1, "approval-1", ShellDecision.APPROVE
                )
            )).state)
            self.assertEqual(ShellRunState.TERMINAL, serve(server, lambda: client.cancel(
                ShellCancelCommand("session-1", 2)
            )).state)
            self.assertEqual(1, gateway.cancellations)

    def test_gateway_exception_becomes_content_free_stable_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            path = root / "shell.sock"
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(FailingGateway()),
            )
            server.open()
            self.addCleanup(server.close)
            client = UnixShellCoreClient(UnixShellClientConfiguration(path))
            with self.assertRaisesRegex(RuntimeError, "shell.core_unavailable") as caught:
                serve(server, lambda: client.ask(ShellAskCommand("request-1", "Help")))
            self.assertNotIn("secret", str(caught.exception))


class Gateway:
    def __init__(self):
        self.cancellations = 0

    def ask(self, command):
        return accepted(command.request_id)

    def snapshot(self, session_id):
        return ShellSessionSnapshot(
            session_id, "request-1", 1, ShellRunState.RUNNING, message="Working"
        )

    def decide(self, command):
        return ShellSessionSnapshot(
            command.session_id, "request-1", 2, ShellRunState.RUNNING,
            message="Approved",
        )

    def cancel(self, command):
        self.cancellations += 1
        result = ShellResult(
            "request-1", ResultStatus.WITHHELD, None, "Cancelled by user"
        )
        return ShellSessionSnapshot(
            command.session_id, "request-1", 3, ShellRunState.TERMINAL,
            result=result,
        )


class FailingGateway:
    def ask(self, command):
        raise RuntimeError("secret provider detail")


def accepted(request_id="request-1"):
    return ShellSessionSnapshot(
        "session-1", request_id, 0, ShellRunState.ACCEPTED, message="Accepted"
    )


def ids(prefix):
    values = iter(range(20))
    return lambda: f"{prefix}-{next(values)}"


def serve(server, operation):
    thread = threading.Thread(target=server.serve_once, daemon=True)
    thread.start()
    try:
        return operation()
    finally:
        thread.join(timeout=2)
        if thread.is_alive():
            raise AssertionError("shell server did not complete")


if __name__ == "__main__":
    unittest.main()
