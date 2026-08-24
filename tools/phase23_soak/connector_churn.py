"""Repeated installed MCP connect, use, disconnect, and process cleanup proof."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.phase23_installed_matrix.mcp_scenario import run_installed_mcp_scenario


def run_connector_churn(
    *, installation: Any, repository: Path, root: Path,
    ollama_url: str, source_model_root: Path,
) -> dict[str, object]:
    reference = repository / "tests/fixtures/mcp_reference_server.py"
    before = _matching_processes(reference)
    scenario = run_installed_mcp_scenario(
        installation=installation,
        repository=repository,
        root=root,
        home=root / "home",
        ollama_url=ollama_url,
        source_model_root=source_model_root,
    )
    after = _matching_processes(reference)
    outbound = scenario["outbound_observation"]
    inbound = scenario["inbound_bridge"]
    return {
        "external_reference_server": str(reference),
        "reference_processes_before": before,
        "reference_processes_after": after,
        "outbound_resource_passed": outbound["resource_observation"]["passed"],
        "outbound_tool_passed": outbound["parameterized_tool"]["passed"],
        "inbound_installed_executable_used": inbound["installed_executable_used"],
        "inbound_visible_tool_count": inbound["visible_tool_count"],
        "configuration_modes": scenario["configuration_modes"],
        "passed": bool(scenario["passed"] and after == before),
    }


def _matching_processes(script: Path) -> tuple[int, ...]:
    marker = str(script.absolute()).encode()
    values = []
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            command = (path / "cmdline").read_bytes()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if marker in command:
            values.append(int(path.name))
    return tuple(sorted(values))
