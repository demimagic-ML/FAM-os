import os
import socket
import unittest
from dataclasses import replace

from fam_os.applications import (
    ApplicationCapabilityRegistry, ConnectorEventKind,
)
from fam_os.applications.transport import (
    AuthenticatedLocalConnection, LocalMessage, LocalMessageKind,
    PeerAuthorizationPolicy, RegistryMessageDispatcher, contract_message,
    decode_contract_message, receive_frame, send_frame,
)
from tests.contract.schema_application_fixtures import (
    action_confirmation, action_preparation, action_proposal, action_result,
    connector_event, connector_registration, observation_request,
    observation_result,
)


class LocalApplicationContractTransportTests(unittest.TestCase):
    def setUp(self):
        self.server_stream, self.client_stream = socket.socketpair(
            socket.AF_UNIX, socket.SOCK_STREAM
        )
        self.addCleanup(self.client_stream.close)
        self.registry = ApplicationCapabilityRegistry()
        self.consumer = Consumer()
        self.connection = AuthenticatedLocalConnection.authenticate(
            self.server_stream,
            PeerAuthorizationPolicy(os.getuid()),
            RegistryMessageDispatcher(self.registry, self.consumer),
            session_id_factory=lambda: "session-1",
        )

    def tearDown(self):
        if self.connection.stream.fileno() >= 0:
            self.connection.close()

    def test_typed_registration_and_all_result_families_round_trip(self):
        self._register()
        exchanges = (
            (LocalMessageKind.OBSERVE, observation_request(),
             LocalMessageKind.OBSERVATION, observation_result()),
            (LocalMessageKind.PREPARE_ACTION, action_preparation(),
             LocalMessageKind.ACTION_PROPOSAL, action_proposal()),
            (LocalMessageKind.CONFIRM_ACTION, action_confirmation(),
             LocalMessageKind.ACTION_RESULT, action_result()),
        )
        for index, (request_kind, request, result_kind, result) in enumerate(exchanges):
            request_id = f"outbound-{index}"
            self.connection.send_request(contract_message(request_id, request_kind, request))
            self.assertEqual(request, decode_contract_message(receive_frame(self.client_stream)))
            send_frame(
                self.client_stream,
                contract_message(f"result-{index}", result_kind, result, request_id),
            )
            self.assertTrue(self.connection.process_next())

        self.assertEqual(
            [observation_result(), action_proposal(), action_result()],
            [item[2] for item in self.consumer.received_values],
        )

    def test_bad_result_does_not_consume_pending_correlation(self):
        self._register()
        self.connection.send_request(contract_message(
            "observe-1", LocalMessageKind.OBSERVE, observation_request()
        ))
        receive_frame(self.client_stream)
        send_frame(self.client_stream, contract_message(
            "bad-1", LocalMessageKind.OBSERVATION, action_result(), "observe-1"
        ))
        with self.assertRaisesRegex(ValueError, "wrong contract type"):
            self.connection.process_next()

        send_frame(self.client_stream, contract_message(
            "wrong-family", LocalMessageKind.ACTION_RESULT,
            action_result(), "observe-1"
        ))
        with self.assertRaisesRegex(ValueError, "kind does not match"):
            self.connection.process_next()

        send_frame(self.client_stream, contract_message(
            "good-1", LocalMessageKind.OBSERVATION,
            observation_result(), "observe-1",
        ))
        self.assertTrue(self.connection.process_next())
        self.assertEqual(observation_result(), self.consumer.received_values[-1][2])

    def test_connector_event_ownership_close_and_initiation_policy(self):
        self._register()
        foreign = replace(connector_event(), connector_id="connector-foreign")
        send_frame(self.client_stream, contract_message(
            "event-foreign", LocalMessageKind.CONNECTOR_EVENT, foreign
        ))
        with self.assertRaises(PermissionError):
            self.connection.process_next()
        self.assertEqual(1, len(self.registry.entries()))

        send_frame(self.client_stream, contract_message(
            "illegal-observe", LocalMessageKind.OBSERVE, observation_request()
        ))
        with self.assertRaisesRegex(PermissionError, "cannot initiate"):
            self.connection.process_next()

        closed = replace(connector_event(), kind=ConnectorEventKind.INSTANCE_CLOSED)
        send_frame(self.client_stream, contract_message(
            "event-close", LocalMessageKind.CONNECTOR_EVENT, closed
        ))
        self.assertTrue(self.connection.process_next())
        self.assertEqual(LocalMessageKind.ACK, receive_frame(self.client_stream).kind)
        self.assertEqual((), self.registry.entries())

    def test_cancellation_and_disconnect_are_safe_and_remove_registration(self):
        self._register()
        for request_id in ("observe-cancel", "observe-disconnect"):
            self.connection.send_request(contract_message(
                request_id, LocalMessageKind.OBSERVE, observation_request()
            ))
            receive_frame(self.client_stream)
        send_frame(self.client_stream, LocalMessage(
            "cancel-1", LocalMessageKind.CANCEL, {"request_id": "observe-cancel"}
        ))
        self.assertTrue(self.connection.process_next())
        self.assertEqual(LocalMessageKind.ACK, receive_frame(self.client_stream).kind)
        self.assertTrue(self.connection.session.cancelled("observe-cancel"))

        self.connection.close()
        self.assertEqual((), self.registry.entries())
        self.assertEqual("observe-disconnect", self.consumer.errors[-1][1])
        self.assertEqual("transport.disconnected", self.consumer.errors[-1][2]["code"])

    def test_core_can_cancel_connector_work_without_creating_new_pending_work(self):
        self._register()
        self.connection.send_request(contract_message(
            "observe-1", LocalMessageKind.OBSERVE, observation_request()
        ))
        receive_frame(self.client_stream)
        self.connection.cancel_request("observe-1", "cancel-1")
        cancellation = receive_frame(self.client_stream)
        self.assertEqual(LocalMessageKind.CANCEL, cancellation.kind)
        self.assertEqual("observe-1", cancellation.payload["request_id"])
        self.assertTrue(self.connection.session.cancelled("observe-1"))
        with self.assertRaisesRegex(ValueError, "pending"):
            self.connection.cancel_request("observe-1", "cancel-2")

    def _register(self):
        send_frame(self.client_stream, contract_message(
            "register-1", LocalMessageKind.REGISTER, connector_registration()
        ))
        self.assertTrue(self.connection.process_next())
        self.assertEqual(LocalMessageKind.ACK, receive_frame(self.client_stream).kind)
        self.assertEqual(1, len(self.registry.entries()))


class Consumer:
    def __init__(self):
        self.received_values = []
        self.errors = []

    def received(self, session, correlation_id, value):
        self.received_values.append((session.session_id, correlation_id, value))

    def transport_error(self, session, correlation_id, payload):
        self.errors.append((session.session_id, correlation_id, payload))


if __name__ == "__main__":
    unittest.main()
