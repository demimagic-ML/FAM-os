"""Short-lived SSE streams for durable Goal Mode snapshots."""

from __future__ import annotations

import json
import time


def stream_goal_events(handler, service, goal_id: str) -> None:
    try:
        snapshot = service.inspect(service.owner_id, goal_id)
    except KeyError:
        handler.send_error(404)
        return
    handler.send_response(200)
    handler._security_headers("text/event-stream; charset=utf-8")
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.close_connection = True
    previous = None
    started = time.monotonic()
    while time.monotonic() - started < 30:
        try:
            payload = json.dumps(snapshot, separators=(",", ":"), sort_keys=True)
            if payload != previous:
                handler.wfile.write(
                    f"event: goal\ndata: {payload}\n\n".encode(),
                )
                handler.wfile.flush()
                previous = payload
            if snapshot["status"] in {"completed", "cancelled", "failed"}:
                return
            time.sleep(0.5)
            if handler._session() is None:
                return
            snapshot = service.inspect(service.owner_id, goal_id)
        except (BrokenPipeError, ConnectionResetError, KeyError, OSError):
            return
