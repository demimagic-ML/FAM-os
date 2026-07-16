# Handoff 0041: Local MCP client adapter

**Date:** 2026-07-16  
**Plan step:** Phase 5.3  
**Status:** Complete  
**Previous handoff:** `0040-authenticated-local-application-transport.md`

## Objective

Consume explicitly configured local MCP resources and tools as bounded,
independently classified Application Fabric capabilities without exposing raw
SDK sessions to models or Core policy.

## Scope completed

- Official Python SDK v1 local stdio provider with same-task clean shutdown.
- Protocol-version and optional exact server-name admission.
- Bounded paginated resource/tool discovery and cursor-cycle rejection.
- Exact resource allowlists and independent observation/action tool policy.
- Stable provider-neutral capability/schema IDs and dynamic registry lifecycle.
- JSON Schema input and structured-output validation.
- Operation timeout, normalized payload bound, and content-free safe failures.
- Live SDK reference server covering resource, observation tool, and action tool.

## Explicitly not completed

- Remote MCP, OAuth, prompts, templates, subscriptions, sampling, elicitation,
  or experimental task extensions.
- Permission-filtered FAM-as-MCP-server ingress (Phase 5.4).
- Connector process sandbox/cgroup composition or pre-decode protocol byte caps.
- Postcondition verification; successful MCP outcomes remain untrusted.

## Architecture and decisions

ADR 0041 pins stable SDK v1 below v2, confines it to one adapter module, and
requires FAM policy rather than MCP annotations to classify effects. The adapter
maps into existing contracts, validates declared schemas, and never constructs a
verified action result. `McpConnectorLifecycle` compensates registration or
refresh failures by removing capabilities and closing the provider.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/mcp/` | Provider port, SDK, values, policy, mapper, client, and registry lifecycle. |
| `tests/unit/test_mcp_client_adapter.py` | Policy, pagination, mapping, schema, bounds, safe failure, and lifecycle tests. |
| `tests/integration/test_mcp_sdk_client.py` | Live official-SDK stdio test. |
| `tests/fixtures/mcp_reference_server.py` | Local MCP resource/tool fixture. |
| `tests/architecture/test_mcp_adapter_boundary.py` | SDK and policy-layer import guard. |
| `docs/protocols/MCP_CLIENT_ADAPTER.md` | Adapter protocol and trust boundary. |
| `docs/decisions/0041-independent-mcp-primitive-classification.md` | Durable mapping decision. |
| `pyproject.toml` | Stable SDK v1 dependency range. |
| `README.md`, `MASTER_PLAN.md`, application/adapter docs | Status and ownership. |

## Public interfaces

- `McpClientSessionPort` and adapter-owned discovery/result values.
- `McpConnectorPolicy`, `McpToolPolicy`, and explicit limits/identity policy.
- `map_discovery`, `McpMappedConnector`, and `McpCapabilityBinding`.
- `McpClientAdapter` and content-safe `McpOperationOutcome`.
- `McpConnectorLifecycle` for registry start/refresh/stop.
- `McpStdioConfiguration` and `OfficialMcpStdioSession`.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_mcp_client_adapter tests.architecture.test_mcp_adapter_boundary
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest tests.integration.test_mcp_sdk_client
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
python3 <AST module/function size gate>
larry index . && larry health .
```

Result: 10 fake/boundary tests and one live SDK test passed. All 438 repository
tests passed in the isolated SDK environment; the system Python run also passed
438 with only the dependency-aware live test skipped. All 35 schema artifacts,
compile, and AST size gates passed. Larry indexed 587 files / 1,687 symbols with
8,025 nodes / 28,227 edges and clean health; the persisted graph was refreshed
with the same totals.

## Evidence and artifacts

- `docs/protocols/MCP_CLIENT_ADAPTER.md`
- `docs/decisions/0041-independent-mcp-primitive-classification.md`
- Live official-SDK test against `tests/fixtures/mcp_reference_server.py`.

## Known limitations and risks

- The SDK allocates a full protocol result before FAM's normalized-result byte
  bound; a malicious same-user server still needs service resource enforcement.
- SDK v2 is expected to stabilize after this decision; migration must be a new
  compatibility change, not an unbounded dependency upgrade.
- Registry state and MCP sessions remain process-local.

## Operational notes

The live test used temporary virtual environment `/tmp/fam-os-mcp-venv` with MCP
SDK 1.28.1 and a local stdio child. No network server, remote credentials, model,
or persistent process was used. The child exited through the MCP shutdown
sequence.

## Recommended next entry point

Begin Phase 5.4. Reuse the official SDK in a separate server-side adapter, but
make ingress an unprivileged Core client surface. Define a narrow Core gateway
port, permission-filter discoverability, bounded tool/resource results, and
tests proving MCP requests cannot directly reach experts, connectors, tools, or
the Supervisor.
