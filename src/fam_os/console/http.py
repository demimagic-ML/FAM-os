"""Loopback-only Console HTTP, session, task, and SSE adapter."""

from __future__ import annotations

import json
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import logging
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from fam_os.console.assets import FONT_ASSETS
from fam_os.console.sessions import ConsoleSessionStore
from fam_os.console.memory_routes import handle_memory_get, handle_memory_post
from fam_os.console.adaptation_routes import (
    handle_adaptation_get,
    handle_adaptation_post,
)
from fam_os.console.task_events import stream_task_events
from fam_os.console.peer_routes import handle_peer_get, handle_peer_post
from fam_os.console.factory_routes import handle_factory_get, handle_factory_post
from fam_os.console.engineering_authority_routes import (
    handle_engineering_authority_get,
    handle_engineering_authority_post,
)
from fam_os.console.integration_environment_routes import (
    handle_integration_environment_get,
    handle_integration_environment_post,
)
from fam_os.console.integration_start_intent_routes import (
    handle_integration_start_intent_get,
)
from fam_os.console.engineering_secret_routes import (
    handle_engineering_secret_get, handle_engineering_secret_post,
)
from fam_os.console.engineering_loop_routes import (
    handle_engineering_loop_get, handle_engineering_loop_post,
)
from fam_os.console.natural_engineering_routes import (
    handle_natural_engineering_get, handle_natural_engineering_post,
)
from fam_os.console.tasks import task_document
from fam_os.console.workspaces import ConsoleWorkspaceApi

DEFAULT_CONSOLE_JSON_BYTES = 262_144
MEMORY_CORRECTION_JSON_BYTES = 8_388_608
_LOGGER = logging.getLogger(__name__)


class ConsoleHttpServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(
        self, address, provider, bootstrap_token: str,
        task_api=None, memory_api=None, adaptation_api=None, peer_api=None,
        factory_api=None, workspace_api=None, engineering_authority_api=None,
        integration_environment_api=None, engineering_secret_api=None,
        engineering_loop_api=None, natural_engineering_api=None,
    ):
        if not ipaddress.ip_address(address[0]).is_loopback:
            raise ValueError("FAM Console must bind only to loopback")
        self.provider = provider
        self.sessions = ConsoleSessionStore(bootstrap_token)
        self.task_api = task_api
        self.memory_api = memory_api
        self.adaptation_api = adaptation_api
        self.peer_api = peer_api
        self.factory_api = factory_api
        self.engineering_authority_api = engineering_authority_api
        self.integration_environment_api = integration_environment_api
        self.engineering_secret_api = engineering_secret_api
        self.engineering_loop_api = engineering_loop_api
        self.natural_engineering_api = natural_engineering_api
        self.workspace_api = workspace_api or ConsoleWorkspaceApi(Path.home())
        super().__init__(address, ConsoleRequestHandler)


class ConsoleRequestHandler(BaseHTTPRequestHandler):
    server: ConsoleHttpServer

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/v1/session":
            self._session_status()
        elif path == "/api/v1/snapshot":
            self._snapshot()
        elif path == "/api/v1/contexts":
            self._contexts()
        elif path == "/api/v1/integrations":
            self._integrations()
        elif path == "/api/v1/workspace":
            self._workspace()
        elif path.startswith("/api/v1/memory/"):
            handle_memory_get(self, path)
        elif path.startswith("/api/v1/adaptation/"):
            handle_adaptation_get(self, path)
        elif path.startswith("/api/v1/peers"):
            handle_peer_get(self, path)
        elif path.startswith("/api/v1/factory/"):
            handle_factory_get(self, path)
        elif path.startswith("/api/v1/engineering/"):
            if handle_natural_engineering_get(self, path):
                return
            if handle_engineering_loop_get(self, path):
                return
            if handle_engineering_secret_get(self, path):
                return
            if handle_integration_start_intent_get(self, path):
                return
            if not handle_integration_environment_get(self, path):
                handle_engineering_authority_get(self, path)
        elif path.endswith("/reversal") and path.startswith("/api/v1/tasks/"):
            self._task_reversal(_task_id(path, "reversal"))
        elif path.endswith("/verification") and path.startswith("/api/v1/tasks/"):
            self._task_verification(_task_id(path, "verification"))
        elif path.endswith("/remote-execution") and path.startswith("/api/v1/tasks/"):
            self._task_remote_execution(_task_id(path, "remote-execution"))
        elif path.endswith("/remote-recovery") and path.startswith("/api/v1/tasks/"):
            self._task_remote_recovery(_task_id(path, "remote-recovery"))
        elif path.endswith("/budget") and path.startswith("/api/v1/tasks/"):
            self._task_budget(_task_id(path, "budget"))
        elif path.endswith("/activity") and path.startswith("/api/v1/tasks/"):
            self._task_activity(_task_id(path, "activity"))
        elif path.startswith("/api/v1/tasks/"):
            self._task_get(path)
        elif path in {"/", "/index.html"}:
            self._static("index.html", "text/html; charset=utf-8")
        elif path == "/styles.css":
            self._static("styles.css", "text/css; charset=utf-8")
        elif path == "/memory.css":
            self._static("memory.css", "text/css; charset=utf-8")
        elif path == "/adaptation.css":
            self._static("adaptation.css", "text/css; charset=utf-8")
        elif path == "/peers.css":
            self._static("peers.css", "text/css; charset=utf-8")
        elif path == "/workspace.css":
            self._static("workspace.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._static("app.js", "text/javascript; charset=utf-8")
        elif path == "/memory.js":
            self._static("memory.js", "text/javascript; charset=utf-8")
        elif path == "/adaptation.js":
            self._static("adaptation.js", "text/javascript; charset=utf-8")
        elif path == "/peers.js":
            self._static("peers.js", "text/javascript; charset=utf-8")
        elif path == "/task_updates.js":
            self._static("task_updates.js", "text/javascript; charset=utf-8")
        elif path == "/conversation.js":
            self._static("conversation.js", "text/javascript; charset=utf-8")
        elif path == "/workspace.js":
            self._static("workspace.js", "text/javascript; charset=utf-8")
        elif path == "/natural_engineering.js":
            self._static("natural_engineering.js", "text/javascript; charset=utf-8")
        elif path.startswith("/fonts/"):
            self._font(path.removeprefix("/fonts/"))
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/v1/session":
            self._exchange_session()
            return
        session = self._mutation_session()
        if session is None:
            return
        try:
            document = self._json_body(_json_limit(path))
            if handle_memory_post(self, path, document):
                return
            if handle_adaptation_post(self, path, document):
                return
            if handle_peer_post(self, path, document):
                return
            if handle_factory_post(self, path, document):
                return
            if handle_natural_engineering_post(
                self, path, document, session.session_id,
            ):
                return
            if handle_engineering_loop_post(self, path, document):
                return
            if handle_integration_environment_post(
                self, path, document, session.session_id,
            ):
                return
            if handle_engineering_secret_post(
                self, path, document, session.session_id,
            ):
                return
            if handle_engineering_authority_post(
                self, path, document, session.session_id,
            ):
                return
            if path == "/api/v1/tasks":
                snapshot = self._tasks().create(document, session.session_id)
            elif path.endswith("/decision") and path.startswith("/api/v1/tasks/"):
                snapshot = self._tasks().decide(_task_id(path, "decision"), document)
            elif path.endswith("/cancel") and path.startswith("/api/v1/tasks/"):
                snapshot = self._tasks().cancel(_task_id(path, "cancel"), document)
            elif path.endswith("/undo") and path.startswith("/api/v1/tasks/"):
                snapshot = self._tasks().reverse(_task_id(path, "undo"), document)
            else:
                self.send_error(404)
                return
        except PermissionError as error:
            self._json(403, {"error": str(error)})
            return
        except (KeyError, TypeError, ValueError) as error:
            self._json(400, {"error": str(error)})
            return
        except Exception:
            _LOGGER.exception("FAM Console POST failed for %s", path)
            self._json(409, {"error": "The task state changed or became unavailable."})
            return
        self._json(200, task_document(snapshot))

    def log_message(self, format: str, *args: object) -> None:
        return

    def _exchange_session(self) -> None:
        if not self._origin_allowed():
            self.send_error(403)
            return
        authorization = self.headers.get("Authorization", "")
        token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
        session = self.server.sessions.exchange(token)
        if session is None:
            self.send_error(401)
            return
        cookie = (
            f"fam_session={session.session_id}; Path=/; HttpOnly; SameSite=Strict"
        )
        self._json(200, {
            "csrf_token": session.csrf_token,
            "expires_at": session.expires_at.isoformat(),
        }, (("Set-Cookie", cookie),))

    def _session_status(self) -> None:
        session = self._session()
        if session is None:
            self.send_error(401)
            return
        self._json(200, {
            "csrf_token": session.csrf_token,
            "expires_at": session.expires_at.isoformat(),
        })

    def _snapshot(self) -> None:
        if self._session() is None:
            self.send_error(401)
            return
        self._json(200, self.server.provider.snapshot().to_dict())

    def _contexts(self) -> None:
        if self._session() is None:
            self.send_error(401)
            return
        self._json(200, {"contexts": self._tasks().contexts()})

    def _integrations(self) -> None:
        if self._session() is None:
            self.send_error(401)
            return
        self._json(200, {"integrations": self._tasks().integrations()})

    def _workspace(self) -> None:
        if self._session() is None:
            self.send_error(401)
            return
        values = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
        if set(values) - {"path"} or len(values.get("path", ())) > 1:
            self._json(400, {"error": "workspace query is invalid"})
            return
        requested = values.get("path", (None,))[0]
        try:
            document = self.server.workspace_api.browse(requested)
        except PermissionError as error:
            self._json(403, {"error": str(error)})
            return
        except (OSError, ValueError) as error:
            self._json(400, {"error": str(error)})
            return
        self._json(200, document)

    def _task_get(self, path: str) -> None:
        if self._session() is None:
            self.send_error(401)
            return
        if path.endswith("/events"):
            self._task_events(_task_id(path, "events"))
            return
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self.send_error(404)
            return
        try:
            snapshot = self._tasks().snapshot(parts[-1])
        except KeyError:
            self.send_error(404)
            return
        self._json(200, task_document(snapshot))

    def _task_reversal(self, task_id: str) -> None:
        if self._session() is None:
            self.send_error(401)
            return
        try:
            status = self._tasks().reversal(task_id)
        except KeyError:
            self.send_error(404)
            return
        self._json(200, status)

    def _task_verification(self, task_id: str) -> None:
        if self._session() is None:
            self.send_error(401)
            return
        try:
            runs = self._tasks().verifications(task_id)
        except KeyError:
            self.send_error(404)
            return
        self._json(200, {"runs": runs})

    def _task_remote_execution(self, task_id: str) -> None:
        if self._session() is None:
            self.send_error(401)
            return
        try:
            document = self._tasks().remote_execution(task_id)
        except KeyError:
            self.send_error(404)
            return
        self._json(200, document)

    def _task_remote_recovery(self, task_id: str) -> None:
        if self._session() is None:
            self.send_error(401)
            return
        try:
            document = self._tasks().remote_recovery(task_id)
        except KeyError:
            self.send_error(404)
            return
        self._json(200, document)

    def _task_budget(self, task_id: str) -> None:
        if self._session() is None:
            self.send_error(401)
            return
        try:
            document = self._tasks().attempt_budget(task_id)
        except KeyError:
            self.send_error(404)
            return
        self._json(200, document)

    def _task_activity(self, task_id: str) -> None:
        if self._session() is None:
            self.send_error(401)
            return
        try:
            document = self._tasks().activity(task_id)
        except KeyError:
            self.send_error(404)
            return
        self._json(200, document)

    def _task_events(self, task_id: str) -> None:
        stream_task_events(self, self._tasks(), task_id)

    def _mutation_session(self):
        session = self._session()
        if session is None:
            self.send_error(401)
            return None
        if not self._origin_allowed() or not self.server.sessions.validate_mutation(
            session.session_id, self.headers.get("X-CSRF-Token", ""),
        ):
            self.send_error(403)
            return None
        return session

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin", "")
        allowed = {
            f"http://127.0.0.1:{self.server.server_port}",
            f"http://localhost:{self.server.server_port}",
        }
        return origin in allowed and self._host_allowed()

    def _session(self):
        if not self._host_allowed():
            return None
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("fam_session")
        return None if morsel is None else self.server.sessions.authenticate(morsel.value)

    def _host_allowed(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0]
        return host in {"127.0.0.1", "localhost", "[::1]"}

    def _tasks(self):
        if self.server.task_api is None:
            raise RuntimeError("Console task service is unavailable")
        return self.server.task_api

    def _json_body(self, maximum=DEFAULT_CONSOLE_JSON_BYTES) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > maximum:
            raise ValueError("JSON request size is invalid")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("JSON request must be an object")
        return value

    def _static(self, name: str, content_type: str) -> None:
        from importlib.resources import files
        payload = files("fam_os.console.static").joinpath(name).read_bytes()
        self._reply(200, content_type, payload)

    def _font(self, name: str) -> None:
        if name not in FONT_ASSETS:
            self.send_error(404)
            return
        self._static(f"fonts/{name}", "font/ttf")

    def _json(self, status: int, value, headers=()) -> None:
        payload = json.dumps(value, default=str, separators=(",", ":")).encode()
        self._reply(status, "application/json", payload, headers)

    def _reply(self, status, content_type, payload, headers=()) -> None:
        self.send_response(status)
        self._security_headers(content_type)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _security_headers(self, content_type: str) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'; frame-ancestors 'none'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")


def _task_id(path: str, suffix: str) -> str:
    parts = path.strip("/").split("/")
    if len(parts) != 5 or parts[-1] != suffix or not parts[-2]:
        raise ValueError("task path is invalid")
    return parts[-2]


def _json_limit(path: str) -> int:
    if path.startswith("/api/v1/memory/documents/") and path.endswith("/correct"):
        return MEMORY_CORRECTION_JSON_BYTES
    return DEFAULT_CONSOLE_JSON_BYTES
