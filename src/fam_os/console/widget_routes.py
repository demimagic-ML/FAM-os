"""Token-authenticated routes for Omarchy and other desktop-shell widgets."""

from __future__ import annotations

import base64
import hashlib
import json
import struct
import time


def handle_widget_get(handler, path: str) -> bool:
    if path not in {"/api/v1/status", "/api/v1/goals/active", "/api/v1/events"}:
        return False
    is_event = path == "/api/v1/events"
    if not handler._widget_authorized(allow_query=is_event):
        handler.send_error(401)
        return True
    api = handler.server.widget_api
    if api is None:
        handler._json(503, {"error": "Desktop widget integration is unavailable."})
        return True
    if is_event:
        _websocket_stream(handler, api)
    elif path == "/api/v1/status":
        handler._json(200, api.status())
    elif path == "/api/v1/goals/active":
        handler._json(200, {"goal": api.active_goal()})
    return True


def handle_widget_post(handler, path: str, document: dict) -> bool:
    widget_paths = {
        "/api/v1/console/open", "/api/v1/candidate/open",
        "/api/v1/agent/submit",
    }
    is_goal = path.startswith("/api/v1/goals/") and path.rsplit("/", 1)[-1] in {
        "pause", "resume", "cancel", "guidance", "candidate-open",
    }
    if path not in widget_paths and not is_goal:
        return False
    if not handler._widget_authorized():
        handler.send_error(401)
        return True
    api = handler.server.widget_api
    if api is None:
        handler._json(503, {"error": "Desktop widget integration is unavailable."})
        return True
    command_id = document.get("commandId")
    if path == "/api/v1/console/open":
        if set(document) != {"commandId"}:
            raise ValueError("console open requires exactly commandId")
        result = api.execute_command(
            command_id, "console.open", api.open_console,
        )
    elif path == "/api/v1/candidate/open":
        if set(document) != {"commandId", "goalId"}:
            raise ValueError("candidate open requires exactly commandId and goalId")
        goal_id = str(document["goalId"])
        result = api.execute_command(
            command_id, "candidate.open", lambda: api.open_candidate(goal_id),
            goal_id=goal_id,
        )
    elif path == "/api/v1/agent/submit":
        required = {
            "commandId", "prompt", "workspace_root", "authority_profile", "goal_mode",
        }
        allowed = required | {"source", "context"}
        if not required.issubset(document) or not set(document).issubset(allowed):
            raise ValueError("agent submission fields are invalid")
        if not isinstance(document["goal_mode"], bool):
            raise ValueError("goal_mode must be boolean")
        result = api.execute_command(
            command_id, "agent.submit", lambda: api.submit(
                document["prompt"], document["workspace_root"],
                document["authority_profile"], goal_mode=document["goal_mode"],
                source=str(document.get("source", "omarchy-agent")),
                transport_context=document.get("context"),
            ),
        )
    else:
        parts = path.strip("/").split("/")
        goal_id, operation = parts[3], parts[4]
        if operation == "candidate-open":
            if set(document) != {"commandId"}:
                raise ValueError("candidate open requires exactly commandId")
            result = api.execute_command(
                command_id, "candidate.open", lambda: api.open_candidate(goal_id),
                goal_id=goal_id,
            )
        else:
            allowed = {"commandId", "content"} if operation == "guidance" else {"commandId"}
            if set(document) != allowed:
                raise ValueError(f"{operation} command fields are invalid")
            action = "guide" if operation == "guidance" else operation
            result = api.execute_command(
                command_id, f"goal.{operation}",
                lambda: api.control(
                    goal_id, action, str(document.get("content", "")),
                ),
                goal_id=goal_id,
            )
    handler._json(202, result)
    return True


def _websocket_stream(handler, api) -> None:
    if handler.headers.get("Upgrade", "").casefold() != "websocket":
        handler._json(426, {"error": "WebSocket upgrade required"}, (("Upgrade", "websocket"),))
        return
    key = handler.headers.get("Sec-WebSocket-Key", "")
    if handler.headers.get("Sec-WebSocket-Version") != "13" or not _valid_websocket_key(key):
        handler.send_error(400)
        return
    accept = base64.b64encode(hashlib.sha1(
        (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii"),
    ).digest()).decode("ascii")
    handler.send_response(101, "Switching Protocols")
    handler.send_header("Upgrade", "websocket")
    handler.send_header("Connection", "Upgrade")
    handler.send_header("Sec-WebSocket-Accept", accept)
    handler.end_headers()
    handler.close_connection = True
    previous = None
    started = time.monotonic()
    while time.monotonic() - started < 60:
        try:
            payload = json.dumps(api.status(), separators=(",", ":"), sort_keys=True)
            if payload != previous:
                handler.wfile.write(_websocket_frame(payload.encode("utf-8")))
                handler.wfile.flush()
                previous = payload
            time.sleep(1.0)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


def _valid_websocket_key(value: str) -> bool:
    try:
        return len(base64.b64decode(value, validate=True)) == 16
    except (ValueError, TypeError):
        return False


def _websocket_frame(payload: bytes) -> bytes:
    length = len(payload)
    if length < 126:
        header = bytes((0x81, length))
    elif length <= 65_535:
        header = bytes((0x81, 126)) + struct.pack("!H", length)
    else:
        header = bytes((0x81, 127)) + struct.pack("!Q", length)
    return header + payload
