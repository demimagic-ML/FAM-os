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
from fam_os.schemas import decode_document, encode_document
from fam_os.shell import (
    ShellEngineeringAuthorityOperation,
    ShellEngineeringContextRequest,
    ShellEngineeringGrantQuery,
)
from fam_os.shell.wire import (
    ShellWireKind,
    decode_engineering_response,
    decode_request,
    engineering_response_message,
    request_message,
)
from tests.contract.schema_shell_fixtures import shell_schema_values


class ShellEngineeringAuthorityWireTests(unittest.TestCase):
    def test_all_authority_requests_and_response_are_strict_registered_roots(self):
        values = shell_schema_values()[-5:]
        kinds = (
            ShellWireKind.ENGINEERING_CONTEXT,
            ShellWireKind.ENGINEERING_ACTIVATE,
            ShellWireKind.ENGINEERING_QUERY,
            ShellWireKind.ENGINEERING_REVOKE,
        )
        for kind, value in zip(kinds, values[:4]):
            self.assertEqual(value, decode_document(encode_document(value)))
            self.assertEqual(
                value, decode_request(request_message("message-1", kind, value)),
            )
        response = values[4]
        message = engineering_response_message("response-1", "request-1", response)
        self.assertEqual(response, decode_engineering_response(message))


class ShellEngineeringAuthorityTransportTests(unittest.TestCase):
    def test_owner_uid_endpoint_issues_context_and_inspects_grant(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            path = root / "shell.sock"
            authority = _AuthorityApi()
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(
                    _UnusedCore(), message_id_factory=_ids("response"),
                    engineering_authority=authority,
                ),
            )
            server.open()
            self.addCleanup(server.close)
            client = UnixShellCoreClient(
                UnixShellClientConfiguration(path), _ids("request"),
            )
            context = ShellEngineeringContextRequest(
                "context-request", "authority-session-1", "owner-1",
                "engineering-grant", "a" * 64, True,
            )
            issued = _serve(server, lambda: client.engineering_context(context))
            self.assertEqual("context-1", issued.context_id)
            self.assertEqual(["authority-session-1"], authority.sessions)
            query = ShellEngineeringGrantQuery(
                "inspect-request", ShellEngineeringAuthorityOperation.INSPECT,
                "grant-engineering-1",
            )
            inspected = _serve(server, lambda: client.engineering_query(query))
            self.assertEqual("grant-engineering-1", inspected.grant.grant_id)
            self.assertTrue(inspected.usable)

    def test_absent_authority_has_stable_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            path = root / "shell.sock"
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(_UnusedCore()),
            )
            server.open()
            self.addCleanup(server.close)
            client = UnixShellCoreClient(UnixShellClientConfiguration(path))
            query = ShellEngineeringGrantQuery(
                "inspect-request", ShellEngineeringAuthorityOperation.INSPECT,
                "grant-engineering-1",
            )
            with self.assertRaisesRegex(RuntimeError, "shell.engineering_unavailable"):
                _serve(server, lambda: client.engineering_query(query))


class _AuthorityApi:
    def __init__(self):
        self.sessions = []
        self.grant = shell_schema_values()[-4].grant

    def issue_context(self, document, session_id):
        self.sessions.append(session_id)
        return {
            "context_id": "context-1",
            "expires_at": datetime(2026, 7, 19, 12, 2, tzinfo=UTC).isoformat(),
        }

    def inspect(self, grant_id):
        return {
            "grant": encode_document(self.grant),
            "reconfirmation_required": False,
            "usable": True,
        }


class _UnusedCore:
    pass


def _ids(prefix):
    values = iter(range(20))
    return lambda: f"{prefix}-{next(values)}"


def _serve(server, operation):
    results = []
    failures = []
    thread = threading.Thread(target=lambda: _capture(operation, results, failures))
    thread.start()
    server.serve_once()
    thread.join(timeout=5)
    if failures:
        raise failures[0]
    return results[0]


def _capture(operation, results, failures):
    try:
        results.append(operation())
    except Exception as error:
        failures.append(error)


if __name__ == "__main__":
    unittest.main()
