"""Exercise opt-in, scope, expiry, isolation, and restart indexing behavior."""

from __future__ import annotations

import time

from tools.phase19_exit.console_client import ConsoleClient


class IndexConsoleClient(ConsoleClient):
    def indexes(self) -> list[dict]:
        return self._request("GET", "/api/v1/memory/indexes")["indexes"]

    def create_index(self, document: dict) -> dict:
        return self._request("POST", "/api/v1/memory/indexes", document)


def first_process_scenario(service, long_root, short_file) -> dict:
    base = f"http://127.0.0.1:{service.port}"
    token = (service.runtime_root / "console.token").read_text().strip()
    client = IndexConsoleClient(base, token)
    isolated = IndexConsoleClient(base, token)
    before = client.indexes()
    denied_without_confirmation = _denied(client, {
        "path": str(long_root), "kind": "folder", "confirmed": False,
    })
    long_receipt = client.create_index({
        "path": str(long_root), "kind": "folder", "recursive": True,
        "allowed_extensions": [".md", ".txt"], "workspace_ids": ["phase20"],
        "expires_in_hours": 24, "confirmed": True,
    })
    short_receipt = client.create_index({
        "path": str(short_file), "kind": "file", "recursive": False,
        "allowed_extensions": [".txt"], "expires_in_seconds": 1,
        "confirmed": True,
    })
    cross_session = isolated.indexes()
    time.sleep(1.3)
    after_expiry = client.indexes()
    return {
        "before": before,
        "denied_without_confirmation": denied_without_confirmation,
        "long_receipt": long_receipt,
        "short_receipt": short_receipt,
        "cross_session": cross_session,
        "after_expiry": after_expiry,
    }


def restarted_process_scenario(service) -> dict:
    base = f"http://127.0.0.1:{service.port}"
    token = (service.runtime_root / "console.token").read_text().strip()
    return {"indexes": IndexConsoleClient(base, token).indexes()}


def _denied(client: IndexConsoleClient, document: dict) -> bool:
    try:
        client.create_index(document)
    except RuntimeError as error:
        detail = str(error)
        return "403" in detail and ("confirmation" in detail or "confirmed=true" in detail)
    return False
