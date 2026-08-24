import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider


class SecretApi:
    def __init__(self): self.session_id = None; self.generation = 0
    def provision(self, document, session_id):
        self.session_id = session_id; self.generation = 1; return self._metadata("active")
    def rotate(self, document, session_id):
        self.session_id = session_id; self.generation += 1; return self._metadata("active")
    def delete(self, document, session_id): return self._metadata("deleted")
    def inspect(self, secret_ref): return self._metadata("active")
    def list(self): return (self._metadata("active"),)
    def audit(self, secret_ref): return {"secret_ref": secret_ref, "events": ()}
    def _metadata(self, state):
        return {"secret_ref": "secret.api", "tool_key": "API_TOKEN",
                "consumer_id": "integration:api", "state": state,
                "generation": self.generation, "created_at": "time", "updated_at": "time"}


class ConsoleEngineeringSecretTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.api = SecretApi()
        self.server = ConsoleHttpServer(
            ("127.0.0.1", 0), LocalConsoleProvider(Path(self.temporary.name)),
            "x" * 32, engineering_secret_api=self.api,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start(); self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temporary.cleanup()

    def test_session_can_provision_list_audit_rotate_and_delete_without_value_response(self):
        opener, csrf = _session(self.base)
        common = {"owner_id": "owner", "secret_ref": "secret.api",
                  "authentication_context_id": "context", "confirmed": True}
        provisioned = _post(opener, self.base + "/api/v1/engineering/secrets/provision", csrf,
                            common | {"tool_key": "API_TOKEN", "consumer_id": "integration:api", "value": "protected"})
        self.assertNotIn("protected", json.dumps(provisioned))
        self.assertTrue(self.api.session_id.startswith("console-"))
        listed = _get(opener, self.base + "/api/v1/engineering/secrets")
        self.assertEqual("secret.api", listed["secrets"][0]["secret_ref"])
        encoded = urllib.parse.quote("secret.api", safe="")
        self.assertEqual([], _get(opener, self.base + f"/api/v1/engineering/secrets/{encoded}/audit")["events"])
        rotated = _post(opener, self.base + f"/api/v1/engineering/secrets/{encoded}/rotate", csrf,
                        common | {"value": "second"})
        self.assertEqual(2, rotated["generation"])
        self.assertEqual("deleted", _post(opener, self.base + f"/api/v1/engineering/secrets/{encoded}/delete", csrf, common)["state"])

    def test_unauthenticated_read_and_path_payload_mismatch_fail(self):
        with self.assertRaises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(self.base + "/api/v1/engineering/secrets")
        self.assertEqual(401, denied.exception.code)
        opener, csrf = _session(self.base)
        with self.assertRaises(urllib.error.HTTPError) as mismatch:
            _post(opener, self.base + "/api/v1/engineering/secrets/secret.other/delete", csrf,
                  {"owner_id": "owner", "secret_ref": "secret.api", "authentication_context_id": "c", "confirmed": True})
        self.assertEqual(403, mismatch.exception.code)


def _session(base):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    request = urllib.request.Request(base + "/api/v1/session", data=b"{}", method="POST",
        headers={"Authorization": "Bearer " + "x" * 32, "Origin": base})
    return opener, json.loads(opener.open(request).read())["csrf_token"]


def _get(opener, url): return json.loads(opener.open(url).read())


def _post(opener, url, csrf, body):
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Origin": url.rsplit("/api/", 1)[0], "X-CSRF-Token": csrf})
    return json.loads(opener.open(request).read())


if __name__ == "__main__": unittest.main()
