"""Loopback-only authenticated HTTP presentation adapter."""

from __future__ import annotations

import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress


class ConsoleHttpServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def __init__(self, address, provider, bearer_token: str):
        if not bearer_token or len(bearer_token) < 32:
            raise ValueError("console bearer token must have at least 32 characters")
        self.provider = provider
        self.bearer_token = bearer_token
        if not ipaddress.ip_address(address[0]).is_loopback:
            raise ValueError("FAM Console must bind only to loopback")
        super().__init__(address, ConsoleRequestHandler)


class ConsoleRequestHandler(BaseHTTPRequestHandler):
    server: ConsoleHttpServer

    def do_GET(self) -> None:
        if self.path == "/api/v1/snapshot":
            self._snapshot()
        elif self.path in {"/", "/index.html"}:
            self._static("index.html", "text/html; charset=utf-8")
        elif self.path == "/styles.css":
            self._static("styles.css", "text/css; charset=utf-8")
        elif self.path == "/app.js":
            self._static("app.js", "text/javascript; charset=utf-8")
        else:
            self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _snapshot(self) -> None:
        if not self._authorized():
            self.send_error(401)
            return
        payload = json.dumps(self.server.provider.snapshot().to_dict(), default=str).encode()
        self._reply(200, "application/json", payload)

    def _static(self, name: str, content_type: str) -> None:
        from importlib.resources import files
        payload = files("fam_os.console.static").joinpath(name).read_bytes()
        self._reply(200, content_type, payload)

    def _authorized(self) -> bool:
        expected = f"Bearer {self.server.bearer_token}"
        supplied = self.headers.get("Authorization", "")
        host = self.headers.get("Host", "").split(":", 1)[0]
        return host in {"127.0.0.1", "localhost", "[::1]"} and hmac.compare_digest(
            supplied, expected,
        )

    def _reply(self, status: int, content_type: str, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)
