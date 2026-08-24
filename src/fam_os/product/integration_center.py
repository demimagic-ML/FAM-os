"""Owner-facing catalog and configuration state for useful integrations."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fam_os.product.composition.mcp_clients import MCP_CONFIG_VERSION, ProductMcpClients


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
    def __init__(self, database, *, state_root: Path | None = None, mcp_clients: ProductMcpClients | None = None) -> None:
        self._database = database
        self._config_path = None if state_root is None else state_root / "config/mcp-clients.json"
        self._mcp_clients = mcp_clients

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
        if executable and integration_id.startswith("mcp.") and self._config_path is not None:
            try:
                self._activate(integration_id, configuration, enabled=enabled)
                status = "ready"
            except Exception as activation_error:
                status = "error"
                error = str(activation_error)
        self._database.execute(
            "INSERT INTO useful_integrations(integration_id,enabled,configuration_json,status,"
            "updated_at,last_checked_at,error) VALUES(?,?,?,?,?,?,?) ON CONFLICT(integration_id) "
            "DO UPDATE SET enabled=excluded.enabled,configuration_json=excluded.configuration_json,"
            "status=excluded.status,updated_at=excluded.updated_at,last_checked_at=excluded.last_checked_at,"
            "error=excluded.error",
            (integration_id, int(enabled), json.dumps(configuration, sort_keys=True), status, now, now, error),
        )
        return self.inspect(integration_id)

    def _activate(self, integration_id: str, configuration: dict, *, enabled: bool) -> None:
        if self._config_path is None or self._mcp_clients is None:
            raise RuntimeError("live MCP activation is unavailable")
        configured: dict[str, dict] = {}
        for item in self.configured()["integrations"]:
            item_id = item["integration_id"]
            if (item["enabled"] and item["status"] == "ready"
                    and isinstance(item_id, str) and item_id.startswith("mcp.")):
                configured[item_id] = item
        if enabled:
            configured[integration_id] = {"configuration": configuration}
        else:
            configured.pop(integration_id, None)
        servers = [
            _mcp_server(item_id, value["configuration"])
            for item_id, value in sorted(configured.items())
        ]
        document = {"contract_version": MCP_CONFIG_VERSION, "servers": servers}
        self._config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        previous = self._config_path.read_bytes() if self._config_path.exists() else None
        descriptor, temporary = tempfile.mkstemp(prefix="mcp-clients.", dir=self._config_path.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(document, handle, sort_keys=True, indent=2)
                handle.write("\n")
            os.replace(temporary, self._config_path)
            try:
                self._mcp_clients.reload_from_file(self._config_path)
            except BaseException:
                if previous is None:
                    self._config_path.unlink(missing_ok=True)
                else:
                    self._config_path.write_bytes(previous)
                    os.chmod(self._config_path, 0o600)
                raise
        finally:
            Path(temporary).unlink(missing_ok=True)

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


def _mcp_server(integration_id: str, configuration: dict) -> dict:
    entry = _entry(integration_id)
    command = shutil.which(entry[2])
    if command is None:
        raise RuntimeError(f"Required executable is unavailable: {entry[2]}")
    suffix = integration_id.removeprefix("mcp.")
    arguments = list(entry[3])
    roots = _roots(configuration)
    if integration_id == "mcp.filesystem":
        if not roots:
            raise ValueError("filesystem integration requires at least one approved root")
        arguments.extend(roots)
        tools = [
            _observe("list_allowed_directories"),
            _observe("read_text_file", "path", "resource_uri", roots),
            _observe("list_directory", "path", "resource_uri", roots),
            _observe("directory_tree", "path", "resource_uri", roots),
        ]
    elif integration_id == "mcp.git":
        root = _single_root(roots, "git integration requires one repository root")
        tools = [_observe(name, "repo_path", "literal", roots, root) for name in (
            "git_status", "git_diff_unstaged", "git_diff_staged", "git_log",
        )]
    elif integration_id == "mcp.fetch":
        tools = [_observe("fetch", "url", "prompt")]
    elif integration_id == "mcp.time":
        timezone_name = configuration.get("timezone", "UTC")
        if not isinstance(timezone_name, str) or not timezone_name.strip():
            raise ValueError("time integration timezone is invalid")
        tools = [_observe("get_current_time", "timezone", "literal", (), timezone_name)]
    else:
        raise ValueError("this MCP integration needs an explicit tool policy before activation")
    workspace_uris = [Path(root).as_uri() for root in roots]
    return {
        "server_id": suffix, "connector_id": f"mcp-{suffix}", "instance_id": f"local-{suffix}",
        "application": {"application_id": f"mcp.{suffix}", "display_name": entry[1]},
        "command": command, "arguments": arguments, "workspace_uris": workspace_uris,
        "allowed_resource_uris": [], "tools": tools,
    }


def _roots(configuration: dict) -> list[str]:
    values = configuration.get("roots", [])
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise ValueError("integration roots must be a list of paths")
    roots = []
    for value in values:
        path = Path(value).expanduser().resolve(strict=True)
        if not path.is_dir():
            raise ValueError("integration roots must be existing directories")
        roots.append(str(path))
    return roots


def _single_root(roots: list[str], message: str) -> str:
    if len(roots) != 1:
        raise ValueError(message)
    return roots[0]


def _observe(name: str, parameter: str | None = None, source: str | None = None,
             scopes=(), literal=None) -> dict:
    bindings = [] if parameter is None else [{"parameter": parameter, "source": source}]
    if bindings and source == "literal":
        bindings[0]["value"] = literal
    return {
        "tool_name": name, "kind": "observation", "required_authority": "observe",
        "resource_scopes": [Path(item).as_uri() for item in scopes],
        "argument_bindings": bindings,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
