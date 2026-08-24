"""Bounded server-sent event streaming for Console task snapshots."""

from __future__ import annotations

import json
import time

from fam_os.console.sse import event_id
from fam_os.console.tasks import task_document


def stream_task_events(handler, task_api, task_id: str) -> None:
    try:
        last = event_id(handler.headers.get("Last-Event-ID"))
        snapshot = task_api.snapshot(task_id)
    except ValueError as error:
        handler._json(400, {"error": str(error)})
        return
    except KeyError:
        handler.send_error(404)
        return
    if last > snapshot.revision:
        handler._json(409, {"error": "Last-Event-ID is ahead of task revision"})
        return
    handler.send_response(200)
    handler._security_headers("text/event-stream; charset=utf-8")
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.close_connection = True
    started = time.monotonic()
    while time.monotonic() - started < 30:
        try:
            if snapshot.revision > last:
                payload = json.dumps(task_document(snapshot), separators=(",", ":"))
                handler.wfile.write(
                    f"id: {snapshot.revision}\nevent: task\ndata: {payload}\n\n".encode(),
                )
                handler.wfile.flush()
                last = snapshot.revision
            if snapshot.state.value == "terminal":
                return
            time.sleep(0.1)
            if handler._session() is None:
                return
            snapshot = task_api.snapshot(task_id)
        except (BrokenPipeError, ConnectionResetError, KeyError, OSError):
            return
