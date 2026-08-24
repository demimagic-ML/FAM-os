import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from fam_os.adapters.git import UnixGitPublicationBroker
from fam_os.core.engineering import (
    GitPublicationApproval, GitRemoteRefObservationRequest,
)
from fam_os.schemas import dumps_document, loads_document
from tests.contract.schema_git_fixtures import git_schema_values


class UnixGitPublicationBrokerTests(unittest.TestCase):
    def test_observation_and_publication_use_typed_credential_opaque_documents(self):
        request = git_schema_values()[7]
        observation = git_schema_values()[8]
        approval = git_schema_values()[3]
        receipt = git_schema_values()[4]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "broker.sock"
            broker = UnixGitPublicationBroker(path)
            seen = []
            first = _server(path, observation, seen)
            self.assertEqual(observation, broker.observe(request))
            first.join(timeout=5)
            second = _server(path, receipt, seen)
            self.assertEqual(receipt, broker.publish(approval))
            second.join(timeout=5)
        self.assertIsInstance(seen[0], GitRemoteRefObservationRequest)
        self.assertIsInstance(seen[1], GitPublicationApproval)
        self.assertEqual("secret.git.origin", seen[0].credential_ref)
        self.assertNotIn("password", dumps_document(seen[0]).casefold())

    def test_rejects_broker_socket_with_broad_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "broker.sock"
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(path))
            os.chmod(path, 0o666)
            self.addCleanup(server.close)
            with self.assertRaisesRegex(PermissionError, "0600"):
                UnixGitPublicationBroker(path).observe(git_schema_values()[7])


def _server(path, response, seen):
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    ready = threading.Event()

    def serve():
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(path))
            os.chmod(path, 0o600)
            server.listen(1)
            ready.set()
            connection, _ = server.accept()
            with connection:
                content = bytearray()
                while True:
                    part = connection.recv(65_536)
                    if not part:
                        break
                    content.extend(part)
                seen.append(loads_document(content.decode().strip()))
                connection.sendall(dumps_document(response).encode())

    thread = threading.Thread(target=serve)
    thread.start()
    ready.wait(timeout=5)
    return thread


if __name__ == "__main__":
    unittest.main()
