import os
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
from fam_os.schemas import decode_document, encode_document
from fam_os.shell import (
    ShellIntegrationEnvironmentControlRequest,
    ShellIntegrationEnvironmentOperation,
    ShellIntegrationEnvironmentQuery,
    ShellIntegrationEnvironmentResponse,
    ShellIntegrationEnvironmentStartRequest,
    ShellIntegrationStartIntentRecord,
)
from fam_os.shell.wire import (
    ShellWireKind,
    decode_integration_environment_response,
    decode_request,
    integration_environment_response_message,
    request_message,
)
from tests.contract.schema_shell_fixtures import shell_schema_values


class ShellIntegrationEnvironmentWireTests(unittest.TestCase):
    def test_requests_and_response_are_strict_registered_roots(self):
        values = tuple(
            item for item in shell_schema_values()
            if isinstance(item, (
                ShellIntegrationEnvironmentStartRequest,
                ShellIntegrationEnvironmentQuery,
                ShellIntegrationEnvironmentControlRequest,
                ShellIntegrationEnvironmentResponse,
            ))
        )
        kinds = (
            ShellWireKind.INTEGRATION_ENVIRONMENT_START,
            ShellWireKind.INTEGRATION_ENVIRONMENT_QUERY,
            ShellWireKind.INTEGRATION_ENVIRONMENT_CONTROL,
        )
        for kind, value in zip(kinds, values[:3]):
            self.assertEqual(value, decode_document(encode_document(value)))
            self.assertEqual(value, decode_request(request_message("message-1", kind, value)))
        response = values[3]
        message = integration_environment_response_message(
            "response-1", "request-1", response,
        )
        self.assertEqual(response, decode_integration_environment_response(message))
        record = response.record
        intent = ShellIntegrationStartIntentRecord(
            "committed", record.plan, record.candidate,
            record.start_result.permit,
        )
        query = ShellIntegrationEnvironmentQuery(
            "intent-query", ShellIntegrationEnvironmentOperation.INTENT_INSPECT,
            "owner-1", record.plan.environment_id,
        )
        self.assertEqual(
            query,
            decode_request(request_message(
                "message-2", ShellWireKind.INTEGRATION_ENVIRONMENT_QUERY, query,
            )),
        )
        intent_response = ShellIntegrationEnvironmentResponse(
            "intent-query", ShellIntegrationEnvironmentOperation.INTENT_INSPECT,
            intent_record=intent,
        )
        self.assertEqual(
            intent_response,
            decode_integration_environment_response(
                integration_environment_response_message(
                    "response-2", "intent-query", intent_response,
                ),
            ),
        )


class ShellIntegrationEnvironmentTransportTests(unittest.TestCase):
    def test_owner_uid_endpoint_inspects_persistent_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); os.chmod(root, 0o700)
            path = root / "shell.sock"
            record = next(
                item.record for item in shell_schema_values()
                if isinstance(item, ShellIntegrationEnvironmentResponse)
                and item.record is not None
            )
            api = Api(record)
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(
                    UnusedCore(), message_id_factory=ids("response"),
                    integration_environment=api,
                ),
            )
            server.open(); self.addCleanup(server.close)
            client = UnixShellCoreClient(
                UnixShellClientConfiguration(path), ids("request"),
            )
            query = ShellIntegrationEnvironmentQuery(
                "inspect-1", ShellIntegrationEnvironmentOperation.INSPECT,
                "owner-1", record.plan.environment_id,
            )
            response = serve(server, lambda: client.integration_environment_query(query))
            self.assertEqual(record, response.record)
            intent_query = ShellIntegrationEnvironmentQuery(
                "intent-1", ShellIntegrationEnvironmentOperation.INTENT_INSPECT,
                "owner-1", record.plan.environment_id,
            )
            intent_response = serve(
                server,
                lambda: client.integration_environment_query(intent_query),
            )
            self.assertEqual("committed", intent_response.intent_record.state)

    def test_absent_facade_has_stable_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); os.chmod(root, 0o700)
            path = root / "shell.sock"
            server = UnixShellServer(
                UnixShellServerConfiguration(path), PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(UnusedCore()),
            )
            server.open(); self.addCleanup(server.close)
            client = UnixShellCoreClient(UnixShellClientConfiguration(path))
            query = ShellIntegrationEnvironmentQuery(
                "list-1", ShellIntegrationEnvironmentOperation.LIST, "owner-1",
            )
            with self.assertRaisesRegex(RuntimeError, "shell.integration_environment_unavailable"):
                serve(server, lambda: client.integration_environment_query(query))


class Api:
    def __init__(self, record):
        self.record = record
        self.intent = ShellIntegrationStartIntentRecord(
            "committed", record.plan, record.candidate,
            record.start_result.permit,
        )
    def inspect(self, owner_id, environment_id): return self.record
    def inspect_intent(self, owner_id, environment_id): return self.intent
    def intents(self, owner_id): return (self.intent,)


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


if __name__ == "__main__":
    unittest.main()
