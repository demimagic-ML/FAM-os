import base64
import json
import socket
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider


class _WidgetApi:
    def __init__(self):
        self.open_count = 0
        self.commands = {}

    def status(self):
        return {
            "contractVersion": "fam.widget/v1",
            "apiVersion": 1,
            "pluginMinVersion": "0.1.0",
            "serviceVersion": "0.1.0",
            "service": "healthy",
            "goal": None,
            "resources": {},
        }

    def execute_command(self, command_id, _action, callback, **_kwargs):
        if command_id not in self.commands:
            self.commands[command_id] = {
                **callback(), "commandId": command_id, "accepted": True,
            }
        return self.commands[command_id]

    def open_console(self):
        self.open_count += 1
        return {"opened": True}


class WidgetTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.api = _WidgetApi()
        self.server = ConsoleHttpServer(
            ("127.0.0.1", 0),
            LocalConsoleProvider(Path(self.temporary.name), "test"),
            "console-token-which-is-long-enough",
            widget_api=self.api,
            widget_token="widget-token-which-is-long-enough",
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temporary.cleanup()

    def test_get_and_idempotent_post_require_token_and_reject_browser_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(self.base + "/api/v1/status")
        self.assertEqual(missing.exception.code, 401)

        request = urllib.request.Request(
            self.base + "/api/v1/status",
            headers={"X-FAM-Widget-Token": "widget-token-which-is-long-enough"},
        )
        self.assertEqual(json.load(urllib.request.urlopen(request))["apiVersion"], 1)

        bad_origin = urllib.request.Request(
            self.base + "/api/v1/status",
            headers={
                "X-FAM-Widget-Token": "widget-token-which-is-long-enough",
                "Origin": "https://attacker.example",
            },
        )
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            urllib.request.urlopen(bad_origin)
        self.assertEqual(rejected.exception.code, 401)

        body = json.dumps({"commandId": "transport-command-0001"}).encode()
        for _ in range(2):
            action = urllib.request.Request(
                self.base + "/api/v1/console/open", data=body, method="POST",
                headers={
                    "Content-Type": "application/json",
                    "X-FAM-Widget-Token": "widget-token-which-is-long-enough",
                },
            )
            self.assertTrue(json.load(urllib.request.urlopen(action))["accepted"])
        self.assertEqual(self.api.open_count, 1)

    def test_websocket_upgrade_uses_query_token_and_returns_bounded_status(self):
        key = base64.b64encode(b"0123456789abcdef").decode()
        with socket.create_connection(
            ("127.0.0.1", self.server.server_port), timeout=3,
        ) as client:
            client.sendall((
                "GET /api/v1/events?token=widget-token-which-is-long-enough HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{self.server.server_port}\r\n"
                "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                "Sec-WebSocket-Version: 13\r\n"
                f"Sec-WebSocket-Key: {key}\r\n\r\n"
            ).encode())
            stream = client.makefile("rb")
            status = stream.readline()
            while stream.readline() not in {b"\r\n", b""}:
                pass
            frame_header = stream.read(2)
            self.assertIn(b"101 Switching Protocols", status)
            self.assertEqual(frame_header[0], 0x81)
            length = frame_header[1] & 0x7F
            if length == 126:
                length = int.from_bytes(stream.read(2), "big")
            elif length == 127:
                length = int.from_bytes(stream.read(8), "big")
            frame = stream.read(length)
        document = json.loads(frame)
        self.assertEqual(document["service"], "healthy")
        self.assertLess(length, 65536)


if __name__ == "__main__":
    unittest.main()
