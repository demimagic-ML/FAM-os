import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from fam_os.adaptation import (
    AdaptationControlStatus,
    LiveAdaptationControlReceipt,
)
from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider
from tests.contract.schema_manifest_fixtures import (
    live_adaptation_control_values,
    live_adaptation_values,
)


class ConsoleAdaptationTests(unittest.TestCase):
    def test_authenticated_owner_can_inspect_disable_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            adaptation = _AdaptationApi()
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
                adaptation_api=adaptation,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(base + "/api/v1/adaptation/status")
                self.assertEqual(401, denied.exception.code)
                opener, csrf = _session(base)
                status = _get(opener, base + "/api/v1/adaptation/status")
                self.assertTrue(status["enabled"])
                snapshots = _get(
                    opener, base + "/api/v1/adaptation/snapshots?offset=0&limit=10",
                )
                self.assertEqual(1, snapshots["total_count"])
                disabled = _post(
                    opener, base + "/api/v1/adaptation/disable", csrf,
                    {"request_id": "disable-1", "confirmed": True},
                )
                self.assertFalse(disabled["state"]["enabled"])
                rollback = _post(
                    opener,
                    base + "/api/v1/adaptation/workflows/intent%3Acode/rollback",
                    csrf, {"request_id": "rollback-1", "confirmed": True},
                )
                self.assertEqual("rollback", rollback["operation"])
                self.assertEqual("intent:code", rollback["target_workflow_id"])
                self.assertEqual(["disable", "rollback"], adaptation.calls)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_mutations_require_csrf_confirmation_and_exact_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
                adaptation_api=_AdaptationApi(),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                opener, csrf = _session(base)
                for body, expected in (
                    ({"request_id": "disable-1", "confirmed": False}, 403),
                    ({"request_id": "disable-2", "confirmed": True, "extra": 1}, 400),
                ):
                    with self.assertRaises(urllib.error.HTTPError) as failure:
                        _post(opener, base + "/api/v1/adaptation/disable", csrf, body)
                    self.assertEqual(expected, failure.exception.code)
                request = urllib.request.Request(
                    base + "/api/v1/adaptation/disable",
                    data=json.dumps({"request_id": "disable-3", "confirmed": True}).encode(),
                    method="POST",
                    headers={"Content-Type": "application/json", "Origin": base},
                )
                with self.assertRaises(urllib.error.HTTPError) as csrf_failure:
                    opener.open(request)
                self.assertEqual(403, csrf_failure.exception.code)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_console_serves_adaptation_panel_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                for path, marker in (
                    ("/", b"Resident intelligence"),
                    ("/adaptation.js", b"FamAdaptation"),
                    ("/adaptation.css", b"adaptation-workspace"),
                ):
                    self.assertIn(marker, urllib.request.urlopen(base + path).read())
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


class _AdaptationApi:
    def __init__(self):
        self.state = live_adaptation_control_values()[0]
        self.snapshot, self.prewarm = live_adaptation_values()
        self.calls = []
        self._receipts = []

    def control_state(self):
        return self.state

    def snapshots(self):
        return (self.snapshot,)

    def receipts(self):
        return (self.prewarm,)

    def health(self):
        return (live_adaptation_control_values()[4],)

    def drift_reports(self):
        return (live_adaptation_control_values()[6],)

    def control_receipts(self):
        return tuple(self._receipts)

    def apply_control(self, request):
        if not request.confirmed:
            raise PermissionError("confirmation required")
        self.calls.append(request.operation.value)
        enabled = False if request.operation.value == "disable" else self.state.enabled
        self.state = replace(
            self.state, revision=self.state.revision + 1, enabled=enabled,
            updated_at=datetime(2026, 7, 17, tzinfo=UTC),
            last_operation=request.operation,
        )
        receipt = LiveAdaptationControlReceipt(
            f"receipt-{request.request_id}", request.request_id, request.operation,
            AdaptationControlStatus.APPLIED, self.state.updated_at,
            self.state.revision - 1, self.state, request.target_workflow_id,
            0, 0, 0, (f"adaptation.{request.operation.value}",),
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
