import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from fam_os.applications.transport import (
    LOCAL_TRANSPORT_VERSION, LocalMessage, LocalMessageKind,
    LocalTransportSession, PeerAuthorizationPolicy, UnixPeerCredentials,
    AuthenticatedLocalConnection,
    UnixApplicationServer, UnixEndpointConfiguration,
    encode_frame, receive_frame, send_frame, unix_peer_credentials,
)
from fam_os.applications.transport.wire import message_from_document


class LocalApplicationTransportTests(unittest.TestCase):
    def test_canonical_frame_round_trip_over_unix_stream(self):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        message = LocalMessage(
            "message-1", LocalMessageKind.OBSERVE,
            {"instance_id": "editor-1", "include": ["selection"]},
        )
        send_frame(left, message)
        self.assertEqual(message, receive_frame(right))
        self.assertEqual(encode_frame(message), encode_frame(message))

    def test_unknown_fields_versions_and_response_without_correlation_reject(self):
        document = {
            "contract_version": LOCAL_TRANSPORT_VERSION,
            "message_id": "message-1",
            "kind": "observe",
            "correlation_id": None,
            "payload": {},
            "extra": True,
        }
        with self.assertRaisesRegex(ValueError, "exactly"):
            message_from_document(document)
        with self.assertRaisesRegex(ValueError, "version"):
            LocalMessage(
                "message-1", LocalMessageKind.OBSERVE,
                contract_version="fam.applications.local/v2",
            )
        with self.assertRaisesRegex(ValueError, "correlation"):
            LocalMessage("message-1", LocalMessageKind.OBSERVATION)

    def test_oversized_and_truncated_frames_reject(self):
        message = LocalMessage("message-1", LocalMessageKind.OBSERVE, {"text": "x" * 100})
        with self.assertRaisesRegex(ValueError, "limit"):
            encode_frame(message, maximum_bytes=32)
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        left.sendall(b"\x00\x00\x00\x08{}")
        left.close()
        with self.assertRaises(EOFError):
            receive_frame(right)

    def test_unix_peer_credentials_bind_to_current_local_user(self):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        peer = unix_peer_credentials(left)
        self.assertEqual(os.getuid(), peer.user_id)
        self.assertTrue(PeerAuthorizationPolicy(os.getuid()).authorize(peer))
        self.assertFalse(PeerAuthorizationPolicy(os.getuid() + 1).authorize(peer))

    def test_session_connector_binding_correlation_and_cancellation(self):
        session = LocalTransportSession("session-1", UnixPeerCredentials(10, 1000, 1000))
        session.bind_connector("connector-1")
        session.bind_connector("connector-1")
        with self.assertRaisesRegex(ValueError, "another connector"):
            session.bind_connector("connector-2")

        session.begin("request-1")
        self.assertTrue(session.cancel("request-1"))
        self.assertTrue(session.cancelled("request-1"))
        with self.assertRaisesRegex(ValueError, "already used"):
            session.begin("request-1")

        session.begin("request-2")
        session.complete("request-2")
        with self.assertRaisesRegex(ValueError, "pending"):
            session.complete("request-2")

    def test_authenticated_connection_registration_request_response_and_cleanup(self):
        server_stream, client_stream = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(client_stream.close)
        dispatcher = Dispatcher()
        connection = AuthenticatedLocalConnection.authenticate(
            server_stream, PeerAuthorizationPolicy(os.getuid()), dispatcher,
            session_id_factory=lambda: "session-1",
        )
        send_frame(client_stream, LocalMessage(
            "register-1", LocalMessageKind.REGISTER,
            {"payload": {"connector_id": "connector-1"}},
        ))
        self.assertTrue(connection.process_next())
        self.assertEqual(LocalMessageKind.ACK, receive_frame(client_stream).kind)

        connection.send_request(LocalMessage(
            "observe-1", LocalMessageKind.OBSERVE, {"capability_id": "editor.observe"}
        ))
        self.assertEqual("observe-1", receive_frame(client_stream).message_id)
        send_frame(client_stream, LocalMessage(
            "observation-1", LocalMessageKind.OBSERVATION, {}, "observe-1"
        ))
        self.assertTrue(connection.process_next())

        connection.send_request(LocalMessage("observe-2", LocalMessageKind.OBSERVE, {}))
        receive_frame(client_stream)
        connection.close()
        self.assertEqual(("observe-2",), dispatcher.disconnected_pending)

    def test_connection_rejects_unauthorized_peer_and_pre_registration_message(self):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        with self.assertRaises(PermissionError):
            AuthenticatedLocalConnection.authenticate(
                left, PeerAuthorizationPolicy(1000), Dispatcher(),
                credential_reader=lambda _: UnixPeerCredentials(1, 2000, 2000),
            )

        connection = AuthenticatedLocalConnection.authenticate(
            left, PeerAuthorizationPolicy(2000), Dispatcher(),
            session_id_factory=lambda: "session-1",
            credential_reader=lambda _: UnixPeerCredentials(1, 2000, 2000),
        )
        send_frame(right, LocalMessage("event-1", LocalMessageKind.CONNECTOR_EVENT, {}))
        with self.assertRaises(PermissionError):
            connection.process_next()

    def test_private_unix_endpoint_serves_and_cleans_up_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            endpoint = Path(directory) / "fam-applications.sock"
            dispatcher = Dispatcher()
            server = UnixApplicationServer(
                UnixEndpointConfiguration(endpoint),
                PeerAuthorizationPolicy(os.getuid()), dispatcher,
            )
            server.open()
            self.assertEqual(0o600, endpoint.stat().st_mode & 0o777)
            thread = threading.Thread(target=server.serve_once)
            thread.start()
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(str(endpoint))
            send_frame(client, LocalMessage(
                "register-1", LocalMessageKind.REGISTER,
                {"payload": {"connector_id": "connector-1"}},
            ))
            self.assertEqual(LocalMessageKind.ACK, receive_frame(client).kind)
            client.close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            server.close()
            self.assertFalse(endpoint.exists())

    def test_endpoint_refuses_existing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            endpoint = Path(directory) / "occupied"
            endpoint.write_text("do not replace", encoding="utf-8")
            server = UnixApplicationServer(
                UnixEndpointConfiguration(endpoint),
                PeerAuthorizationPolicy(os.getuid()), Dispatcher(),
            )
            with self.assertRaises(FileExistsError):
                server.open()
            self.assertEqual("do not replace", endpoint.read_text(encoding="utf-8"))


class Dispatcher:
    def __init__(self):
        self.disconnected_pending = None

    def dispatch(self, session, message):
        if message.kind in {LocalMessageKind.REGISTER, LocalMessageKind.CANCEL}:
            return LocalMessage(
                f"ack-{message.message_id}", LocalMessageKind.ACK, {}, message.message_id
            )
        return None

    def disconnected(self, session, pending_request_ids):
        self.disconnected_pending = pending_request_ids


if __name__ == "__main__":
    unittest.main()
