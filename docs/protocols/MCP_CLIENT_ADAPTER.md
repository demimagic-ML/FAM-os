# Local MCP Client Adapter

## Scope

Phase 5.3 lets FAM_OS consume explicitly configured local MCP servers without
making MCP the Application Fabric or giving models a protocol session. The
adapter supports local stdio servers through the official Python SDK v1, maps
approved resources and tools into dynamic Application Fabric registrations,
and returns bounded untrusted operation outcomes for later Core policy and
verification.

Remote HTTP/SSE MCP, OAuth, prompts, sampling, elicitation, resource templates,
subscriptions, and task extensions are outside this step. The provider port has
no sampling or elicitation method, so a server cannot obtain model or permission
authority through this client.

## Dependency and protocol compatibility

`pyproject.toml` pins `mcp>=1.27,<2`. The upper bound follows the official SDK's
current guidance while v2 remains pre-release. The adapter dynamically imports
the SDK only in `adapters/mcp/sdk.py`; every other module and all domain code use
small adapter-owned values.

The configured policy lists allowed negotiated protocol versions and may pin
the expected server name. A mismatch rejects before primitive discovery. The
live reference test negotiated `2025-11-25` with SDK 1.28.1.

## Discovery and mapping

Discovery follows every `resources/list` and `tools/list` cursor with bounded
page and primitive counts. Repeated cursors, excessive pages, duplicate
capabilities, invalid JSON Schemas, and empty approved results reject.

| MCP primitive | Application Fabric mapping |
|---|---|
| Explicitly allowlisted resource URI | Observation capability scoped to that URI |
| Explicitly classified observation tool | Observation capability requiring observe authority |
| Explicitly classified action tool | Action capability with configured authority, confirmation, reversibility, and deterministic postconditions |
| Unlisted resource/tool | Not registered and not invocable |

MCP tool annotations are untrusted hints. `readOnlyHint`, `destructiveHint`, and
other server claims never select the capability kind or authority. The local
policy independently classifies each tool. Capability and schema identifiers
are stable SHA-256-derived identifiers, while the exact schemas remain in the
adapter binding used for validation.

`McpConnectorLifecycle` atomically registers the approved mapped set in the
dynamic capability registry. Refresh replaces the connector-owned set. Start or
refresh failure closes the session and safely retires the registration; stop is
idempotent.

## Invocation boundary

Arguments are validated against the server-declared JSON Schema before a
provider call. If the tool declares an output schema, structured output is
required and validated. Resource and tool results are normalized to immutable
JSON and limited by configured serialized bytes. Timeouts, provider exceptions,
tool errors, invalid output, and oversized results become stable error codes
without returning raw provider error content.

An outcome marked `succeeded` means only that MCP transport completed, the
server did not mark an error, and declared shape/size checks passed. It is still
untrusted and is not an `ActionResult.VERIFIED`. Core confirmation,
postconditions, verification, audit, and final-result release remain mandatory.

The official SDK parses a complete protocol message before the adapter can
apply its normalized-result byte limit. Connector process cgroups, sandboxing,
and transport-level read limits remain productization hardening; the current
stdio child still receives the SDK's restricted inherited environment plus only
explicit configured variables.

## Live evidence

`tests/fixtures/mcp_reference_server.py` exposes one resource, one observation
tool, and one action tool over stdio. The integration test starts it with the
official SDK, negotiates, discovers, maps, reads/invokes all three primitives,
validates structured output, and performs the protocol shutdown sequence.

## References

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [MCP resources specification](https://modelcontextprotocol.io/specification/2025-11-25/server/resources)
