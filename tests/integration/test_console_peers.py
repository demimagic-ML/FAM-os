import hashlib
import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider
from fam_os.fabric import PeerManagementReceipt
from fam_os.schemas import dumps_document
from tests.contract.schema_manifest_fixtures import device_identity_values

NOW = datetime(2026, 7, 17, tzinfo=UTC)


class ConsolePeerTests(unittest.TestCase):
    def test_console_serves_device_fabric_panel_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                for path, marker in (
                    ("/", b"Run confirmed remote task"),
                    ("/peers.js", b"remote_authority"),
                    ("/peers.css", b"peer-route-ticket"),
                ):
                    self.assertIn(marker, urllib.request.urlopen(base + path).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_authenticated_owner_can_list_probe_set_privacy_and_revoke(self):
        with tempfile.TemporaryDirectory() as directory:
            peer = _PeerApi()
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
                peer_api=peer,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(base + "/api/v1/peers")
                self.assertEqual(401, denied.exception.code)
                opener, csrf = _session(base)
                listed = _get(opener, base + "/api/v1/peers?offset=0&limit=10")
                self.assertEqual(1, listed["total_count"])
                enrollment = listed["peers"][0]["enrollment_id"]
                probed = _post(
                    opener, base + f"/api/v1/peers/{enrollment}/probe", csrf,
                    {"request_id": "probe-1"},
                )
                self.assertTrue(probed["trusted"])
                privacy = _post(
                    opener, base + f"/api/v1/peers/{enrollment}/privacy", csrf,
                    {
                        "request_id": "privacy-1", "expected_revision": 0,
                        "confirmed": True, "reason_code": "owner.configured",
                        "maximum_context_bytes": 4096,
                        "sensitivities": ["private"], "purpose_ids": ["assist"],
                        "workspace_ids": ["workspace:test"],
                        "raw_content_allowed": False,
                    },
                )
                self.assertEqual("set_privacy", privacy["operation"])
                context = _post(
                    opener, base + f"/api/v1/peers/{enrollment}/context", csrf,
                    {
                        "request_id": "context-1", "target_expert_id": "expert.code",
                        "capability_declaration_id": "capability-1",
                        "expected_privacy_revision": 1, "purpose_id": "assist",
                        "workspace_id": "workspace:test", "sensitivity": "private",
                        "intent_id": "intent.code", "capability_ids": ["code.generate"],
                        "assurance_id": "verified", "maximum_output_bytes": 4096,
                        "raw_fragments": [], "confirmed": False,
                    },
                )
                self.assertEqual(enrollment, context["enrollment_id"])
                self.assertEqual("context-1", peer.context_requests[0].request_id)
                revoked = _post(
                    opener, base + f"/api/v1/peers/{enrollment}/revoke", csrf,
                    {
                        "request_id": "revoke-1", "expected_revision": 1,
                        "confirmed": True, "reason_code": "owner.revoked",
                    },
                )
                self.assertEqual("revoke", revoked["operation"])
                receipts = _get(opener, base + "/api/v1/peers/receipts")
                self.assertEqual(2, receipts["total_count"])
                evidence = _get(opener, base + "/api/v1/peers/context-evidence")
                self.assertEqual(0, evidence["total_count"])
                self.assertEqual(["probe-1"], peer.probes)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_mutations_require_csrf_confirmation_and_exact_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            peer = _PeerApi()
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
                peer_api=peer,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                opener, csrf = _session(base)
                enrollment = peer.entry.enrollment_id
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    _post(
                        opener, base + f"/api/v1/peers/{enrollment}/revoke", csrf,
                        {
                            "request_id": "revoke-denied", "expected_revision": 1,
                            "confirmed": False, "reason_code": "owner.revoked",
                        },
                    )
                self.assertEqual(403, denied.exception.code)
                with self.assertRaises(urllib.error.HTTPError) as malformed:
                    _post(
                        opener, base + f"/api/v1/peers/{enrollment}/revoke", csrf,
                        {
                            "request_id": "revoke-extra", "expected_revision": 1,
                            "confirmed": True, "reason_code": "owner.revoked", "extra": 1,
                        },
                    )
                self.assertEqual(400, malformed.exception.code)
                request = urllib.request.Request(
                    base + f"/api/v1/peers/{enrollment}/probe",
                    data=b'{"request_id":"probe-no-csrf"}', method="POST",
                    headers={"Content-Type": "application/json", "Origin": base},
                )
                with self.assertRaises(urllib.error.HTTPError) as csrf_denied:
                    opener.open(request)
                self.assertEqual(403, csrf_denied.exception.code)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


class _PeerApi:
    owner_id = "owner"

    def __init__(self):
        self.entry = device_identity_values()[-1]
        self.probes = []
        self.context_requests = []
        self._receipts = []

    def trusted_peers(self):
        return (self.entry,)

    def peer(self, enrollment_id):
        if enrollment_id != self.entry.enrollment_id:
            raise KeyError(enrollment_id)
        return self.entry

    def probe(self, enrollment_id, request_id=None):
        self.probes.append(request_id)
        return self.peer(enrollment_id)

    def control_receipts(self):
        return tuple(self._receipts)

    def context_evidence(self):
        return ()

    def send_context(self, request):
        self.context_requests.append(request)
        return self.entry

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


def _session(base):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    exchange = urllib.request.Request(
        base + "/api/v1/session", data=b"{}", method="POST",
        headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
    )
    session = json.loads(opener.open(exchange).read())
    return opener, session["csrf_token"]


def _get(opener, url):
    return json.loads(opener.open(url).read())


def _post(opener, url, csrf, body):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={
            "Content-Type": "application/json", "Origin": url.rsplit("/api/", 1)[0],
            "X-CSRF-Token": csrf,
        },
    )
    return json.loads(opener.open(request).read())


if __name__ == "__main__":
    unittest.main()
