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


class ConsoleEngineeringAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.api = _EngineeringAuthorityApi()
        self.server = ConsoleHttpServer(
            ("127.0.0.1", 0), LocalConsoleProvider(Path(self.temporary.name)),
            "x" * 32, engineering_authority_api=self.api,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def test_authenticated_owner_can_issue_inspect_audit_and_revoke(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(self.base + "/api/v1/engineering/grants/grant-1")
        self.assertEqual(401, denied.exception.code)
        opener, csrf = _session(self.base)
        issued = _post(opener, self.base + "/api/v1/engineering/authentication-contexts", csrf, {
            "owner_id": "owner-1", "purpose": "engineering-grant",
            "payload_sha256": "a" * 64, "confirmed": True,
        })
        self.assertEqual("context-1", issued["context_id"])
        inspected = _get(opener, self.base + "/api/v1/engineering/grants/grant-1")
        self.assertEqual("grant-1", inspected["grant_id"])
        audited = _get(opener, self.base + "/api/v1/engineering/grants/grant-1/audit")
        self.assertEqual([], audited["decisions"])
        revoked = _post(
            opener, self.base + "/api/v1/engineering/grants/grant-1/revoke", csrf,
            {"owner_id": "owner-1", "confirmed": True},
        )
        self.assertEqual("revoked", revoked["state"])
        self.assertTrue(self.api.session_ids[0].startswith("console-"))

    def test_mutations_require_csrf_and_confirmation(self) -> None:
        opener, csrf = _session(self.base)
        body = {
            "owner_id": "owner-1", "purpose": "engineering-grant",
            "payload_sha256": "a" * 64, "confirmed": True,
        }
        request = urllib.request.Request(
            self.base + "/api/v1/engineering/authentication-contexts",
            data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "Origin": self.base},
        )
        with self.assertRaises(urllib.error.HTTPError) as missing_csrf:
            opener.open(request)
        self.assertEqual(403, missing_csrf.exception.code)
        body["confirmed"] = False
        with self.assertRaises(urllib.error.HTTPError) as unconfirmed:
            _post(
                opener, self.base + "/api/v1/engineering/authentication-contexts",
                csrf, body,
            )
        self.assertEqual(403, unconfirmed.exception.code)


class _EngineeringAuthorityApi:
    def __init__(self):
        self.session_ids = []

    def issue_context(self, document, session_id):
        if document["confirmed"] is not True:
            raise PermissionError("confirmation required")
        self.session_ids.append(session_id)
        return {"context_id": "context-1"}

    def inspect(self, grant_id):
        return {"grant_id": grant_id, "state": "active"}

    def audit(self, grant_id):
        return {"grant_id": grant_id, "decisions": []}

    def revoke(self, grant_id, document):
        return {"grant_id": grant_id, "state": "revoked"}

    def activate(self, document, session_id):
        self.session_ids.append(session_id)
        return {"state": "active"}


def _session(base):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    request = urllib.request.Request(
        base + "/api/v1/session", data=b"{}", method="POST",
        headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
    )
    document = json.loads(opener.open(request).read())
    return opener, document["csrf_token"]


def _get(opener, url):
    return json.loads(opener.open(url).read())


def _post(opener, url, csrf, body):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={
            "Content-Type": "application/json",
            "Origin": url.rsplit("/api/", 1)[0],
            "X-CSRF-Token": csrf,
        },
    )
    return json.loads(opener.open(request).read())


if __name__ == "__main__":
    unittest.main()
