"""Installed outbound and inbound MCP application-weaving qualification."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path

from fam_os.adapters.mcp import McpStdioConfiguration, OfficialMcpStdioSession

from tools.phase19_exit.console_client import ConsoleClient

from .service import CandidateService


_REFERENCE_URI = "fam-test://document"
_REFERENCE_SERVER_ID = "phase23-reference"
_REFERENCE_APPLICATION_ID = "org.fam.phase23.mcp-reference"
_INGRESS_CLIENT_ID = "phase23-installed-client"


def run_installed_mcp_scenario(
    *, installation, repository: Path, root: Path, home: Path,
    ollama_url: str, source_model_root: Path,
) -> dict[str, object]:
    """Drive both MCP directions through one real installed product service."""
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    state = root / "state"
    _write_outbound_configuration(state, repository)
    _write_ingress_configuration(state)
    service = CandidateService(
        installation, state, root / "run", ollama_url=ollama_url,
        source_model_root=source_model_root, home=home,
    )
    with service:
        outbound = _outbound_observation(service)
        inbound = asyncio.run(_inbound_bridge(installation, service.runtime_root))
    return {
        "outbound_observation": outbound,
        "inbound_bridge": inbound,
        "configuration_modes": {
            "mcp_clients": _mode(state / "config/mcp-clients.json"),
            "mcp_ingress": _mode(state / "config/mcp-ingress.json"),
        },
        "passed": bool(outbound["passed"] and inbound["passed"]),
    }


def _write_outbound_configuration(state: Path, repository: Path) -> Path:
    path = state / "config/mcp-clients.json"
    document = {
        "contract_version": "fam.product.mcp-clients/v1alpha1",
        "servers": [{
            "server_id": _REFERENCE_SERVER_ID,
            "connector_id": "phase23-mcp-reference",
            "instance_id": "phase23-mcp-reference-instance",
            "application": {
                "application_id": _REFERENCE_APPLICATION_ID,
                "display_name": "Phase 23 MCP reference",
                "vendor": "FAM_OS qualification",
                "version": "1",
            },
            "command": str(Path(sys.executable).absolute()),
            "arguments": [str(repository / "tests/fixtures/mcp_reference_server.py")],
            "environment": {},
            "working_directory": str(repository),
            "allowed_resource_uris": [_REFERENCE_URI],
            "tools": [{
                "tool_name": "lookup",
                "kind": "observation",
                "required_authority": "observe",
                "argument_bindings": [{
                    "parameter": "query",
                    "source": "prompt",
                }],
            }],
            "workspace_uris": [],
            "expected_server_name": "FAM MCP reference",
            "operation_timeout_seconds": 30,
        }],
    }
    return _write_private_json(path, document)


def _write_ingress_configuration(state: Path) -> Path:
    path = state / "config/mcp-ingress.json"
    document = {
        "contract_version": "fam.product.mcp-ingress/v1alpha1",
        "enabled": True,
        "clients": [{
            "client_id": _INGRESS_CLIENT_ID,
            "principal_id": "phase23-installed-principal",
            "capabilities": ["fam.ask", "fam.ask.verified"],
            "session_ttl_seconds": 3600,
        }],
    }
    return _write_private_json(path, document)


def _write_private_json(path: Path, document: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def _outbound_observation(service: CandidateService) -> dict[str, object]:
    client = _console_client(service)
    resource_capability = _resource_capability_id()
    context = client.wait_for_context(resource_capability, timeout=30)
    accepted = client.create(
        "phase23-installed-mcp-outbound",
        "Using only the observed MCP resource, return exactly: resident neural fabric",
        [_application_context(context, resource_capability), _uri_context()],
        [resource_capability], True,
    )
    terminal = client.wait_for_terminal(accepted["session_id"], timeout=180)
    result = terminal.get("result") or {}
    content = str(result.get("content") or "")
    resource_passed = bool(
        context.get("application_id") == _REFERENCE_APPLICATION_ID
        and result.get("assurance") in {"grounded", "verified"}
        and "resident neural fabric" in content.lower()
    )
    tool_capability = _tool_capability_id("lookup")
    tool_context = client.wait_for_context(tool_capability, timeout=30)
    tool_prompt = "phase23 typed binding probe"
    tool_accepted = client.create(
        "phase23-installed-mcp-arguments", tool_prompt,
        [_application_context(tool_context, tool_capability)],
        [tool_capability], True,
    )
    tool_terminal = client.wait_for_terminal(
        tool_accepted["session_id"], timeout=180,
    )
    tool_result = tool_terminal.get("result") or {}
    tool_content = str(tool_result.get("content") or "")
    tool_passed = bool(
        tool_result.get("assurance") in {"grounded", "verified"}
        and tool_prompt.upper() in tool_content.upper()
        and next(
            (item for item in tool_terminal.get("steps", ())
             if item.get("kind") == "observe"), {}
        ).get("state") == "succeeded"
    )
    return {
        "resource_observation": {
            "session_id": accepted["session_id"],
            "capability_id": resource_capability,
            "resource_uri": _REFERENCE_URI,
            "terminal": terminal,
            "observed_content_present": "resident neural fabric" in content.lower(),
            "passed": resource_passed,
        },
        "parameterized_tool": {
            "session_id": tool_accepted["session_id"],
            "capability_id": tool_capability,
            "binding_source": "prompt",
            "terminal": tool_terminal,
            "observed_bound_value_present": tool_prompt.upper() in tool_content.upper(),
            "passed": tool_passed,
        },
        "application_id": context.get("application_id"),
        "connector_instance": context.get("resource_ref"),
        "passed": bool(resource_passed and tool_passed),
    }


async def _inbound_bridge(installation, runtime_root: Path) -> dict[str, object]:
    executable = (installation.prefix / "bin/fam-os").absolute()
    configuration = McpStdioConfiguration(
        executable,
        (
            "--prefix", str(installation.prefix.absolute()),
            "mcp", "serve", "--client-id", _INGRESS_CLIENT_ID,
            "--runtime-root", str(runtime_root.absolute()),
        ),
        (),
        (installation.prefix / "active").absolute(),
    )
    session = await OfficialMcpStdioSession.open(configuration)
    try:
        server = await session.initialize()
        page = await session.list_tools()
        by_name = {item.name: item for item in page.items}
        ask_name = _ingress_tool_name("fam.ask")
        verified_name = _ingress_tool_name("fam.ask.verified")
        if ask_name not in by_name or verified_name not in by_name:
            raise RuntimeError("installed MCP ingress did not expose its allowlisted tools")
        ordinary = await session.call_tool(
            ask_name, {"prompt": "Reply briefly that installed MCP ingress reached FAM Core."},
        )
        verified = await session.call_tool(
            verified_name,
            {"prompt": "Return an unverified statement through the verified MCP tool."},
        )
    finally:
        await session.close()
    ordinary_payload = _thaw(ordinary.structured_content or {})
    verified_payload = _thaw(verified.structured_content or {})
    installed_executable = (
        executable.is_file()
        and executable.is_relative_to(installation.prefix.absolute())
    )
    return {
        "server": {
            "name": server.name,
            "version": server.version,
            "protocol_version": server.protocol_version,
        },
        "installed_executable": str(executable),
        "installed_executable_used": installed_executable,
        "visible_tool_count": len(page.items),
        "ordinary": {
            "is_error": ordinary.is_error,
            "result": ordinary_payload,
        },
        "verified": {
            "is_error": verified.is_error,
            "result": verified_payload,
        },
        "passed": bool(
            server.name == "FAM_OS"
            and installed_executable
            and len(page.items) == 2
            and not ordinary.is_error
            and ordinary_payload.get("status") == "completed"
            and isinstance(ordinary_payload.get("content"), str)
            and verified.is_error
            and verified_payload.get("status") == "withheld"
            and verified_payload.get("content") is None
        ),
    }


def _console_client(service: CandidateService) -> ConsoleClient:
    token = (service.runtime_root / "console.token").read_text().strip()
    return ConsoleClient(f"http://127.0.0.1:{service.port}", token)


def _resource_capability_id() -> str:
    digest = hashlib.sha256(_REFERENCE_URI.encode()).hexdigest()[:20]
    return f"mcp.{_REFERENCE_SERVER_ID}.resource.{digest}"


def _tool_capability_id(tool_name: str) -> str:
    digest = hashlib.sha256(tool_name.encode()).hexdigest()[:20]
    return f"mcp.{_REFERENCE_SERVER_ID}.tool.{digest}"


def _ingress_tool_name(capability_id: str) -> str:
    digest = hashlib.sha256(capability_id.encode()).hexdigest()[:24]
    return f"fam_{digest}"


def _application_context(value: dict, capability_id: str) -> dict:
    return {
        "context_id": value["context_id"],
        "kind": "application",
        "resource_ref": value["resource_ref"],
        "display_name": value["display_name"],
        "capability_ids": [
            item for item in value["capability_ids"]
            if item == capability_id
        ],
    }


def _uri_context() -> dict:
    return {
        "context_id": "phase23-mcp-resource",
        "kind": "uri",
        "resource_ref": _REFERENCE_URI,
        "display_name": "Phase 23 MCP resource",
        "capability_ids": [],
    }


def _mode(path: Path) -> str:
    return oct(path.stat().st_mode & 0o777)


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
