# ADR 0041: Independently classify and bound local MCP client capabilities

**Status:** Accepted  
**Date:** 2026-07-16

## Decision

Use the official Python MCP SDK v1 behind an adapter-owned session port for
explicitly configured local stdio servers. Pin the dependency to
`mcp>=1.27,<2` while SDK v2 remains pre-release.

Map only exact allowlisted resources and exact independently classified tools
into Application Fabric capabilities. Never derive observe/action authority,
confirmation, reversibility, or postconditions from MCP annotations. Validate
declared input and structured output schemas, bound pages, primitive counts,
operation time, and normalized payload bytes, and convert provider failures to
stable content-free errors.

Treat successful MCP invocation as an untrusted adapter outcome rather than a
verified application action. Keep prompts, sampling, elicitation, remote
transports, SDK sessions, and model handles outside this adapter surface.

## Consequences

- Structured MCP resources and tools participate in the same registry as
  native and generic application capabilities.
- A malicious server cannot label its own tool safe and thereby gain authority.
- SDK/protocol churn is confined to `adapters/mcp/sdk.py` and adapter values.
- The official stdio shutdown lifecycle must enter and exit in the same async
  task; the wrapper and live test preserve this requirement.
- The post-decode payload bound does not prevent the SDK from first allocating
  a large protocol message; sandbox/cgroup and lower transport limits remain
  later hardening.

## Evidence

- `src/fam_os/adapters/mcp/`
- `tests/unit/test_mcp_client_adapter.py`
- `tests/integration/test_mcp_sdk_client.py`
- `tests/architecture/test_mcp_adapter_boundary.py`
- `docs/protocols/MCP_CLIENT_ADAPTER.md`
