import os
import socket
import threading
import unittest

from fam_os.applications import ApplicationCapabilityRegistry
from fam_os.applications.transport import (
    AuthenticatedLocalConnection, ConnectorRequestBroker, LocalMessageKind,
    PeerAuthorizationPolicy, contract_message, decode_contract_message,
    receive_frame, send_frame,
)
from tests.contract.schema_application_fixtures import (
    connector_registration, observation_request, observation_result,
)


class ConnectorRequestBrokerTests(unittest.TestCase):
    def test_registered_connector_receives_correlated_core_request(self):
        server_stream, client_stream = socket.socketpair(socket.AF_UNIX)
        self.addCleanup(client_stream.close)
        ids = iter(("outbound-1",))
        broker = ConnectorRequestBroker(
            ApplicationCapabilityRegistry(), id_factory=lambda: next(ids),
        )
        connection = AuthenticatedLocalConnection.authenticate(
            server_stream, PeerAuthorizationPolicy(os.getuid()), broker,
            session_id_factory=lambda: "session-1",
        )
        broker.connected(connection)
        self.addCleanup(connection.close)
        send_frame(client_stream, contract_message(
            "register-1", LocalMessageKind.REGISTER, connector_registration(),
        ))
        connection.process_next()
        receive_frame(client_stream)

        worker = threading.Thread(
            target=self._connector_reply, args=(client_stream,), daemon=True,
        )
        worker.start()
        result_holder = []
        requester = threading.Thread(target=lambda: result_holder.append(
            broker.observe("connector-vscode", observation_request())
        ))
        requester.start()
        connection.process_next()
        requester.join(timeout=2)
        worker.join(timeout=2)
        self.assertEqual(observation_result(), result_holder[0])

    @staticmethod
    def _connector_reply(stream):
        request = receive_frame(stream)
        decode_contract_message(request)
        send_frame(stream, contract_message(
            "result-1", LocalMessageKind.OBSERVATION,
            observation_result(), request.message_id,
        ))


if __name__ == "__main__":
    unittest.main()
