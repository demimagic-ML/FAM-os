import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider
from fam_os.expert_factory import (
    build_verified_failure_trace,
    discover_failure_clusters,
)


class ConsoleFactoryTests(unittest.TestCase):
    def test_authenticated_owner_can_inspect_content_free_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            factory = _FactoryApi()
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)),
                "x" * 32, factory_api=factory,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(base + "/api/v1/factory/proposals")
                self.assertEqual(401, denied.exception.code)
                opener = _session(base)
                proposals = _get(opener, base + "/api/v1/factory/proposals")
                traces = _get(opener, base + "/api/v1/factory/traces")
                clusters = _get(opener, base + "/api/v1/factory/clusters")
                self.assertEqual(1, len(proposals["proposals"]))
                self.assertEqual(2, len(traces["traces"]))
                self.assertEqual(1, len(clusters["clusters"]))
                encoded = json.dumps((proposals, traces, clusters))
                self.assertNotIn("prompt", encoded)
                self.assertNotIn("candidate content", encoded)
                self.assertFalse(proposals["proposals"][0]["training_authorized"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_factory_mutations_require_csrf_exact_fields_and_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            factory = _FactoryApi()
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)),
                "x" * 32, factory_api=factory,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                opener, csrf = _session_with_csrf(base)
                body = {
                    "request_id": "grant-1",
                    "proposal_id": factory.proposals()[0].proposal_id,
                    "capability_id": "intent.code",
                    "source_kinds": ["verified_fixture"],
                    "workspace_scopes": ["workspace:test"],
                    "sensitivities": ["private"],
                    "maximum_source_bytes": 1000,
                    "maximum_examples": 10,
                    "lifetime_seconds": 3600,
                    "confirmed": True,
                }
                response = _post(
                    opener, base + "/api/v1/factory/capture-grants", csrf, body,
                )
                self.assertEqual(factory.proposals()[0].proposal_id, response["proposal_id"])
                self.assertEqual("create_capture_grant", factory.calls[-1][0])

                source = _post(
                    opener, base + "/api/v1/factory/sources", csrf,
                    {
                        "grant_id": "grant-1", "source_id": "source-safe-1",
                        "source_family_id": "source-family-safe-1",
                        "source_kind": "verified_fixture",
                        "workspace_scope": "workspace:test",
                        "sensitivity": "private", "license_id": "owner-authored",
                        "input_text": "Unsafe request",
                        "reference_output": "I can't help with that.",
                        "evaluation_kind": "safety",
                        "evaluation_verifier": "safe_refusal",
                        "evaluation_requirement_id": "acceptance.safety.refusal",
                        "confirmed": True,
                    },
                )
                self.assertEqual(factory.proposals()[0].proposal_id, source["proposal_id"])
                self.assertEqual("capture_source", factory.calls[-1][0])
                self.assertEqual(
                    "safety", factory.calls[-1][1]["evaluation_kind"].value,
                )

                with self.assertRaises(urllib.error.HTTPError) as incomplete:
                    _post(
                        opener, base + "/api/v1/factory/sources", csrf,
                        {
                            "grant_id": "grant-1", "source_id": "source-bad-1",
                            "source_family_id": "source-family-bad-1",
                            "source_kind": "verified_fixture",
                            "workspace_scope": "workspace:test",
                            "sensitivity": "private",
                            "license_id": "owner-authored",
                            "input_text": "Unsafe request",
                            "reference_output": "No.",
                            "evaluation_kind": "safety", "confirmed": True,
                        },
                    )
                self.assertEqual(400, incomplete.exception.code)

                probed = _post(
                    opener,
                    base + "/api/v1/factory/training-environments/probe",
                    csrf, {"confirmed": True},
                )
                self.assertEqual(factory.proposals()[0].proposal_id, probed["proposal_id"])
                started = _post(
                    opener, base + "/api/v1/factory/training-jobs", csrf,
                    {
                        "request_id": "training-start-1",
                        "approval_id": "training-approval-1",
                        "confirmed": True,
                    },
                )
                self.assertEqual(factory.proposals()[0].proposal_id, started["proposal_id"])
                for name in (
                    "training-environments", "training-jobs",
                    "training-terminals", "training-admissions",
                ):
                    collection = _get(opener, f"{base}/api/v1/factory/{name}")
                    self.assertEqual(1, len(collection[name.replace("-", "_")]))

                with self.assertRaises(urllib.error.HTTPError) as fields:
                    _post(
                        opener, base + "/api/v1/factory/capture-grants", csrf,
                        {**body, "extra": True},
                    )
                self.assertEqual(400, fields.exception.code)
                request = urllib.request.Request(
                    base + "/api/v1/factory/capture-grants",
                    data=json.dumps(body).encode(), method="POST",
                    headers={"Content-Type": "application/json", "Origin": base},
                )
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    opener.open(request)
                self.assertEqual(403, denied.exception.code)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


class _FactoryApi:
    def __init__(self):
        now = datetime(2026, 7, 17, tzinfo=UTC)
        self._traces = tuple(_trace(index, now) for index in (1, 2))
        self._clusters, self._proposals = discover_failure_clusters(self._traces)
        self.calls = []

    def traces(self):
        return self._traces

    def clusters(self):
        return self._clusters

    def proposals(self):
        return self._proposals

    def create_capture_grant(self, **values):
        if not values["confirmed"]:
            raise PermissionError("confirmation required")
        self.calls.append(("create_capture_grant", values))
        return self._proposals[0]

    def capture_source(self, **values):
        self.calls.append(("capture_source", values))
        return self._proposals[0]

    def training_environments(self):
        return self._proposals

    def training_jobs(self):
        return self._proposals

    def training_terminals(self):
        return self._proposals

    def training_admissions(self):
        return self._proposals

    def probe_training_environment(self, **values):
        self.calls.append(("probe_training_environment", values))
        return self._proposals[0]

    def start_training(self, **values):
        self.calls.append(("start_training", values))
        return self._proposals[0]


def _trace(index: int, now: datetime):
    return build_verified_failure_trace(
        verification_id=f"verification-{index}", request_id=f"request-{index}",
        candidate_id=f"candidate-{index}", capability_id="intent.code",
        failed_requirement_id="acceptance.python.tests",
        verifier_id="python.deterministic-tests.v1",
        verifier_artifact_sha256="a" * 64,
        candidate_sha256=f"{index}" * 64, model_ref="qwen3:1.7b",
        expert_tier="economical", release_id="release-1", signer_key_id="key-1",
        observed_at=now + timedelta(seconds=index),
    )


def _session(base: str):
    return _session_with_csrf(base)[0]


def _session_with_csrf(base: str):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    request = urllib.request.Request(
        base + "/api/v1/session", data=b"{}", method="POST",
        headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
    )
    response = json.loads(opener.open(request).read())
    return opener, response["csrf_token"]


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
