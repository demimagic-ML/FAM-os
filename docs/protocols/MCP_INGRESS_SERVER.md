# Authenticated Permission-Filtered MCP Ingress

## Purpose

Phase 5.4 lets a compatible local application use selected FAM capabilities
through an MCP server. The server is an unprivileged client surface, like FAM
Shell or the future local API. It never owns admission, model selection,
application authority, execution, verification, or final-result policy.

```text
local MCP application
        |
one-time authenticated session
        |
permission-filtered MCP tools
        |
LifecycleCoreIngressGateway
        |
RequestAdmissionService -> CoreTaskExecutor -> TaskResult
```

## Authentication

FAM issues a cryptographically random, short-lived bootstrap capability for an
existing `RequestIdentity`. Only its SHA-256 digest is retained. Successful
authentication consumes the token exactly once and constructs the ingress
session; direct unauthenticated construction rejects. The token is not an MCP
argument, tool result, model input, or log field.

The initial in-memory token registry is appropriate for a same-process local
composition and tests. `McpIngressAuthenticator` is a port so the installed
service can redeem bootstrap capabilities through its protected local authority
service. Passing the token to a standalone process and multi-user transport
binding require later deployment composition. The underlying Core authority
grant is checked again on every discovery and invocation, so bootstrap-token
expiry does not extend or replace user permission.

## Permission-filtered discovery

`LifecycleCoreIngressGateway.visible_capabilities()` resolves the identity's
current authority grant and returns only active granted `IngressCapability`
entries. The MCP tool list is rebuilt for each request. Stable opaque MCP tool
names are derived from capability IDs, while the underlying ID is retained as
metadata for diagnostics.

If permission expires or is revoked after discovery, the tool disappears and a
subsequent call is denied before Core execution. Catalog size is bounded. A
catalog or gateway failure returns no discoverable tools rather than exposing an
internal exception.

## Mandatory Core lifecycle

Every MCP call becomes a `CoreIngressRequest`. The Core gateway:

1. Resolves the published capability.
2. Validates parameters against its trusted schema.
3. Creates a least-privilege `TaskRequest` requiring exactly that capability.
4. Calls `RequestAdmissionService`, including authority expiry/revocation and
   replay protection.
5. Invokes `CoreTaskExecutor` only with an `AdmittedTaskRequest`.
6. Enforces request/result identity and verification-required release policy.

The MCP adapter imports the gateway port and Core contracts only. Architecture
tests prohibit direct imports of experts, routing, Supervisor, Verification
Fabric, or the application connector transport. The official SDK has no direct
reference to any execution provider.

## Bounds and safe results

The MCP and Core boundaries both validate input schemas. Request bytes, result
bytes, and visible tools are bounded. Provider exceptions become stable safe
failures without raw exception text. MCP results expose only:

```text
request_id, status, verified, content, reason, evidence_ids, failure_code
```

Failed and withheld Core results cannot carry content because `TaskResult`
enforces that invariant. If a capability requires verification and its executor
returns merely completed content, the gateway converts it to content-free
`WITHHELD`.

Sampling and elicitation handlers are not registered. MCP therefore cannot ask
FAM to run a model or grant permission outside the normal Core request.

## SDK surface

`OfficialMcpIngressServer` uses the official SDK v1 low-level server so tool
schemas and dynamic permission filtering remain explicit. It supports SDK
streams and stdio once an authenticated ingress engine has been composed. The
live test connects an official `ClientSession` over memory streams, lists the
filtered tool, invokes it, and observes a verified Core-shaped result.

## References

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP authorization specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
