import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider
from fam_os.core.engineering import CandidateWorkspace, IntegrationEnvironmentStatus
from fam_os.schemas import encode_document
from tests.contract.schema_integration_environment_fixtures import (
    NOW,
    integration_environment_schema_values,
)


class Stored:
    def __init__(self, plan, candidate, result, receipt, state="active"):
        self.plan, self.candidate = plan, candidate
        self.start_result, self.latest_receipt = result, receipt
        self.state = state


class Intent:
    def __init__(self, stored):
        self.plan, self.candidate = stored.plan, stored.candidate
        self.permit = stored.start_result.permit
        self.recovery_receipt = None
        self.state = "committed"


class Api:
    _owner_id = "owner-1"

    @property
    def owner_id(self):
        return self._owner_id

    def __init__(self, stored):
        self.stored = stored
        self.intent = Intent(stored)
        self.session_id = None

    def active(self, owner_id):
        return (self.stored,)

    def inspect(self, owner_id, environment_id):
        return self.stored

    def receipts(self, owner_id, environment_id):
        return (self.stored.latest_receipt,)

    def intents(self, owner_id): return (self.intent,)
    def inspect_intent(self, owner_id, environment_id): return self.intent

    def start(self, owner_id, plan, candidate, grant_id, principal_id, session_id, cancelled):
        self.session_id = session_id
        return self.stored.start_result

    def cleanup(self, owner_id, environment_id):
        from dataclasses import replace
        return replace(
            self.stored.latest_receipt, status=IntegrationEnvironmentStatus.CLEANED,
            cleanup_evidence_ids=("removed:test",),
        )

    reconcile = cleanup


class ConsoleIntegrationEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        _spec, plan, _permit, receipt, result = integration_environment_schema_values()
        candidate = CandidateWorkspace(
            plan.candidate_id, plan.task_id, "baseline-1", "/owner",
            plan.candidate_root, NOW, "copy", "a" * 64, (),
        )
        self.api = Api(Stored(plan, candidate, result, receipt))
        self.server = ConsoleHttpServer(
            ("127.0.0.1", 0), LocalConsoleProvider(Path(self.temporary.name)),
            "x" * 32, integration_environment_api=self.api,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.temporary.cleanup()

    def test_session_owner_can_start_inspect_audit_and_cleanup(self):
        with self.assertRaises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(self.base + "/api/v1/engineering/environments")
        self.assertEqual(401, denied.exception.code)
        opener, csrf = _session(self.base)
        active = _get(opener, self.base + "/api/v1/engineering/environments")
        self.assertEqual("active", active["environments"][0]["state"])
        started = _post(
            opener, self.base + "/api/v1/engineering/environments/start", csrf,
            {
                "owner_id": "owner-1", "plan": encode_document(self.api.stored.plan),
                "candidate": encode_document(self.api.stored.candidate),
                "grant_id": "grant-1", "principal_id": "fam-core", "confirmed": True,
            },
        )
        self.assertIn("integration-environment-start", started["schema_id"])
        self.assertTrue(self.api.session_id.startswith("console-"))
        audited = _get(
            opener, self.base + "/api/v1/engineering/environments/environment-1/audit",
        )
        self.assertEqual(1, len(audited["receipts"]))
        intents = _get(
            opener,
            self.base + "/api/v1/engineering/environment-start-intents",
        )
        self.assertEqual("committed", intents["start_intents"][0]["state"])
        intent = _get(
            opener,
            self.base + "/api/v1/engineering/environment-start-intents/environment-1",
        )
        self.assertEqual(
            self.api.stored.start_result.permit.permit_id,
            intent["permit"]["payload"]["permit_id"],
        )
        cleaned = _post(
            opener, self.base + "/api/v1/engineering/environments/environment-1/cleanup",
            csrf, {"owner_id": "owner-1", "confirmed": True},
        )
        self.assertEqual("cleaned", cleaned["payload"]["status"])

    def test_mutation_requires_confirmation(self):
        opener, csrf = _session(self.base)
        with self.assertRaises(urllib.error.HTTPError) as denied:
            _post(
                opener, self.base + "/api/v1/engineering/environments/environment-1/reconcile",
                csrf, {"owner_id": "owner-1", "confirmed": False},
            )
        self.assertEqual(403, denied.exception.code)


def _session(base):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    request = urllib.request.Request(
        base + "/api/v1/session", data=b"{}", method="POST",
        headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
    )
    return opener, json.loads(opener.open(request).read())["csrf_token"]


def _get(opener, url):
    return json.loads(opener.open(url).read())


def _post(opener, url, csrf, body):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Origin": url.rsplit("/api/", 1)[0], "X-CSRF-Token": csrf},
    )
    return json.loads(opener.open(request).read())


if __name__ == "__main__":
    unittest.main()
