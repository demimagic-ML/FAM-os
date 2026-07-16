# ADR 0042: Treat MCP ingress only as an authenticated Core client

**Status:** Accepted  
**Date:** 2026-07-16

## Decision

Expose selected FAM capabilities through an official-SDK local MCP server only
after a one-time opaque bootstrap capability authenticates an existing
`RequestIdentity`. Store only token digests and consume a token on first use.

Make discovery permission-filtered and re-evaluate visibility on every call.
Route every invocation through a Core-owned gateway that validates its trusted
input schema, creates a least-privilege `TaskRequest`, calls
`RequestAdmissionService`, and passes only `AdmittedTaskRequest` to the executor.

Return only bounded `TaskResult` fields. Preserve failed/withheld content safety
and withhold completed-but-unverified content whenever the published capability
requires verification. Do not register sampling or elicitation handlers and do
not let the MCP adapter import execution-provider layers.

## Consequences

- MCP clients gain interoperable FAM tools without acquiring model, desktop,
  connector, Supervisor, or permission authority.
- Permission revocation after tool discovery takes effect at invocation.
- Replay protection and final release invariants are shared with every other
  Core client instead of reimplemented in MCP.
- The current one-time token registry is process-local; installed cross-process
  redemption and Unix peer/session binding remain deployment hardening.
- Dynamic low-level SDK tools are used instead of FastMCP-decorated static
  functions so each session sees its own current permission catalog.

## Evidence

- `src/fam_os/core/ingress/`
- `src/fam_os/adapters/mcp/ingress/`
- `tests/unit/test_core_ingress_gateway.py`
- `tests/unit/test_mcp_ingress.py`
- `tests/integration/test_mcp_ingress_sdk_server.py`
- `tests/architecture/test_mcp_ingress_boundary.py`
- `docs/protocols/MCP_INGRESS_SERVER.md`
