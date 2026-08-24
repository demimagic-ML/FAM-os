"""Owner-facing catalog and configuration state for useful integrations."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone


INTEGRATION_CATALOG = (
    ("mcp.filesystem", "Filesystem", "npx", ("-y", "@modelcontextprotocol/server-filesystem"), "Local files and folders"),
    ("mcp.git", "Git", "uvx", ("mcp-server-git",), "Repository status, diffs, and history"),
    ("mcp.fetch", "Web fetch", "uvx", ("mcp-server-fetch",), "Read web pages for research"),
    ("mcp.time", "Time", "uvx", ("mcp-server-time",), "Time and timezone calculations"),
    ("mcp.browser", "Browser", "npx", ("-y", "@playwright/mcp"), "Browser research and interaction"),
    ("caldav.calendar", "Calendar", "caldav", (), "Calendar events and schedules"),
    ("imap.email", "Email", "python3", ("-m", "fam_os_integrations.email"), "Read and draft email"),
    ("postgres.database", "PostgreSQL", "python3", ("-m", "fam_os_integrations.postgres"), "Query approved databases"),
)


class IntegrationCenter:
    def __init__(self, database) -> None:
        self._database = database

    def catalog(self) -> dict[str, list[dict[str, object]]]:
        configured = {item["integration_id"]: item for item in self.configured()["integrations"]}
        return {"integrations": [self._catalog_item(item, configured.get(item[0])) for item in INTEGRATION_CATALOG]}

    def configured(self) -> dict[str, list[dict[str, object]]]:
        rows = self._database.fetchall(
            "SELECT integration_id,enabled,configuration_json,status,last_checked_at,error "
            "FROM useful_integrations ORDER BY integration_id",
        )
        return {"integrations": [{
            "integration_id": row[0], "enabled": bool(row[1]),
            "configuration": json.loads(row[2]), "status": row[3],
            "last_checked_at": row[4], "error": row[5],
        } for row in rows]}

    def configure(self, integration_id: str, document: dict) -> dict[str, object]:
        entry = _entry(integration_id)
        enabled = document.get("enabled", True)
        configuration = document.get("configuration", {})
        if not isinstance(enabled, bool) or not isinstance(configuration, dict):
            raise ValueError("integration configuration is invalid")
        if len(json.dumps(configuration)) > 16_384:
            raise ValueError("integration configuration is too large")
        now = _now()
        executable = shutil.which(entry[2])
        status = "ready" if executable else "missing_runtime"
        error = None if executable else f"Required executable is unavailable: {entry[2]}"
        self._database.execute(
            "INSERT INTO useful_integrations(integration_id,enabled,configuration_json,status,"
            "updated_at,last_checked_at,error) VALUES(?,?,?,?,?,?,?) ON CONFLICT(integration_id) "
            "DO UPDATE SET enabled=excluded.enabled,configuration_json=excluded.configuration_json,"
            "status=excluded.status,updated_at=excluded.updated_at,last_checked_at=excluded.last_checked_at,"
            "error=excluded.error",
            (integration_id, int(enabled), json.dumps(configuration, sort_keys=True), status, now, now, error),
        )
        return self.inspect(integration_id)

    def test(self, integration_id: str) -> dict[str, object]:
        current = self.inspect(integration_id)
        return self.configure(integration_id, {
            "enabled": current["enabled"], "configuration": current["configuration"],
        })

    def inspect(self, integration_id: str) -> dict[str, object]:
        for item in self.configured()["integrations"]:
            if item["integration_id"] == integration_id:
                return item
        raise KeyError("integration has not been configured")

    @staticmethod
    def _catalog_item(entry, configured):
        executable = shutil.which(entry[2])
        return {
            "integration_id": entry[0], "title": entry[1],
            "command": entry[2], "arguments": entry[3], "description": entry[4],
            "runtime_available": executable is not None,
            "configured": configured is not None, "state": configured,
        }


def _entry(integration_id: str):
    for item in INTEGRATION_CATALOG:
        if item[0] == integration_id:
            return item
    raise KeyError("integration is not in the qualified catalog")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
