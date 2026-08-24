import os
import tempfile
import threading
import unittest
from pathlib import Path

from fam_os.adapters.shell import (
    ShellRequestDispatcher, UnixShellClientConfiguration, UnixShellCoreClient,
    UnixShellServer, UnixShellServerConfiguration,
)
from fam_os.applications.transport.auth import PeerAuthorizationPolicy
from fam_os.schemas import decode_document, encode_document
from fam_os.shell import (
    ShellEngineeringSecretMutation, ShellEngineeringSecretOperation,
    ShellEngineeringSecretQuery, ShellEngineeringSecretResponse,
)
from fam_os.shell.wire import (
    ShellWireKind, decode_engineering_secret_response, decode_request,
    engineering_secret_response_message, request_message,
)
from tests.contract.schema_shell_fixtures import shell_schema_values


class ShellEngineeringSecretWireTests(unittest.TestCase):
    def test_requests_and_response_are_strict_registered_roots(self):
        values = shell_schema_values()
        query = next(item for item in values if isinstance(item, ShellEngineeringSecretQuery))
        mutation = next(item for item in values if isinstance(item, ShellEngineeringSecretMutation))
        response = next(item for item in values if isinstance(item, ShellEngineeringSecretResponse))
        for kind, value in (
            (ShellWireKind.ENGINEERING_SECRET_QUERY, query),
            (ShellWireKind.ENGINEERING_SECRET_MUTATION, mutation),
        ):
            self.assertEqual(value, decode_document(encode_document(value)))
            self.assertEqual(value, decode_request(request_message("message-1", kind, value)))
        message = engineering_secret_response_message("response-1", "request-1", response)
        self.assertEqual(response, decode_engineering_secret_response(message))


class ShellEngineeringSecretTransportTests(unittest.TestCase):
    def test_owner_uid_endpoint_provisions_and_returns_metadata_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); os.chmod(root, 0o700)
            path = root / "shell.sock"; api = Api()
            server = UnixShellServer(
                UnixShellServerConfiguration(path), PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(
                    UnusedCore(), message_id_factory=ids("response"),
                    engineering_secrets=api,
                ),
            )
            server.open(); self.addCleanup(server.close)
            client = UnixShellCoreClient(UnixShellClientConfiguration(path), ids("request"))
            command = ShellEngineeringSecretMutation(
                "provision-1", ShellEngineeringSecretOperation.PROVISION,
                "authority-session-1", "owner", "context-1", "secret.api",
                "API_TOKEN", "integration:api", "protected-value", True,
            )
            response = serve(server, lambda: client.engineering_secret_mutation(command))
            self.assertEqual("secret.api", response.metadata.secret_ref)
            self.assertNotIn("protected-value", repr(response))
            self.assertEqual("authority-session-1", api.session_id)

    def test_absent_facade_has_stable_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); os.chmod(root, 0o700); path = root / "shell.sock"
            server = UnixShellServer(
                UnixShellServerConfiguration(path), PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(UnusedCore()),
            )
            server.open(); self.addCleanup(server.close)
            client = UnixShellCoreClient(UnixShellClientConfiguration(path))
            query = ShellEngineeringSecretQuery(
                "list-1", ShellEngineeringSecretOperation.LIST,
            )
            with self.assertRaisesRegex(RuntimeError, "shell.engineering_secret_unavailable"):
                serve(server, lambda: client.engineering_secret_query(query))


class Api:
    def __init__(self): self.session_id = None
    def provision(self, document, session_id):
        self.session_id = session_id
        return _metadata()


def _metadata():
    return {"secret_ref": "secret.api", "tool_key": "API_TOKEN",
            "consumer_id": "integration:api", "state": "active", "generation": 1,
            "created_at": "2026-07-19T00:00:00+00:00",
            "updated_at": "2026-07-19T00:00:00+00:00"}


class UnusedCore: pass


def ids(prefix):
    values = iter(range(20)); return lambda: f"{prefix}-{next(values)}"


def serve(server, operation):
    results, failures = [], []
    def run():
        try: results.append(operation())
        except Exception as error: failures.append(error)
    thread = threading.Thread(target=run); thread.start(); server.serve_once(); thread.join(5)
    if failures: raise failures[0]
    return results[0]


if __name__ == "__main__": unittest.main()
