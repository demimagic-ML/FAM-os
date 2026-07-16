# Handoff 0042: Authenticated MCP Core ingress

**Date:** 2026-07-16  
**Plan step:** Phase 5.4  
**Status:** Complete  
**Previous handoff:** `0041-local-mcp-client-adapter.md`

## Objective

Expose selected FAM capabilities to compatible local MCP clients while proving
that authentication, current permission, Core admission, verification, and safe
result policy cannot be bypassed.

## Scope completed

- Core-owned ingress capability/request contracts, catalog, gateway, and executor port.
- Current-grant permission-filtered capability discovery.
- Trusted-schema validation, least-privilege `TaskRequest`, admission, replay,
  identity, and verification-required result enforcement.
- Random short-lived one-time bootstrap capabilities stored only as digests.
- Bounded dynamic MCP tools and content-free adapter/gateway failures.
- Official SDK low-level server with no sampling or elicitation surface.
- Live official `ClientSession` list/call proof over SDK memory streams.

## Explicitly not completed

- Installed cross-process bootstrap redemption, persistent token authority, or
  multi-user transport binding.
- Remote MCP/OAuth and general network exposure.
- Full production task executor composition; tests use the gateway port fake.
- FAM Shell UI (Phase 5.8).

## Architecture and decisions

ADR 0042 makes MCP ingress only a Core client. It authenticates before server
construction, reevaluates the authority grant on discovery/call, and routes each
request through `RequestAdmissionService`. The adapter sees only `CoreIngressGateway`
and cannot import experts, routing, Supervisor, verification, or connector
transport implementation. A completed result is withheld if the capability
declares verification required.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/ingress/` | Capability contracts, registry, gateway ports, and admission service. |
| `src/fam_os/adapters/mcp/ingress/` | One-time auth, bounded engine, and official SDK server. |
| `tests/unit/test_core_ingress_gateway.py` | Admission, replay, permission, schema, and release tests. |
| `tests/unit/test_mcp_ingress.py` | Authentication, recheck, bounds, and safe-error tests. |
| `tests/integration/test_mcp_ingress_sdk_server.py` | Official SDK client/server proof. |
| `tests/architecture/test_mcp_ingress_boundary.py` | Layer bypass guards. |
| `docs/protocols/MCP_INGRESS_SERVER.md` | Ingress and authentication protocol. |
| `docs/decisions/0042-mcp-ingress-is-a-core-client.md` | Durable boundary decision. |
| `README.md`, component docs, `MASTER_PLAN.md` | Status and ownership. |

## Public interfaces

- `IngressCapability`, `CoreIngressRequest`, and `CoreIngressGateway`.
- `CoreTaskExecutor`, `IngressCapabilityRegistry`, and in-memory catalog.
- `LifecycleCoreIngressGateway`.
- `McpIngressAuthenticator` and `OneTimeMcpIngressTokens`.
- `AuthenticatedMcpIngress`, `McpIngressLimits`, tool/outcome values.
- `OfficialMcpIngressServer` for streams or stdio after authentication.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_core_ingress_gateway tests.unit.test_mcp_ingress tests.architecture.test_mcp_ingress_boundary
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest tests.integration.test_mcp_ingress_sdk_server
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
python3 <AST module/function size gate>
larry index . && larry health .
```

Result: 12 fake/boundary tests and one live SDK test passed. All 451 tests
passed in the MCP environment; system Python passed 451 with the two SDK live
tests skipped. All 35 schemas matched and compile/AST gates passed. Larry indexed
604 files / 1,750 symbols with 8,159 nodes / 29,062 edges and clean health; the
persisted graph was refreshed with the same totals.

## Evidence and artifacts

- `docs/protocols/MCP_INGRESS_SERVER.md`
- `docs/decisions/0042-mcp-ingress-is-a-core-client.md`
- `tests/integration/test_mcp_ingress_sdk_server.py`

## Known limitations and risks

- The in-memory bootstrap registry does not cross a standalone process boundary;
  deployment must redeem through a protected local authority service.
- A one-time token authenticates session construction but is not itself a
  peer-credential or package-attestation mechanism.
- The full executor is a later composition; the gateway already enforces that
  it receives only admitted work and safe final results.

## Operational notes

The live test used only in-memory SDK streams. No socket, network port, external
application, persistent token, model, or child process was created.

## Recommended next entry point

Begin Phase 5.5. Define provider-neutral discovery snapshots and Linux adapters
for `/proc`, desktop entry files, session/compositor window/focus providers, and
safe launch metadata. Keep all discovery read-only; launch authority belongs to
later action adapters and Core permission.
