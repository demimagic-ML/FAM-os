# Handoff 0139: Permission-filtered production MCP ingress

**Date:** 2026-07-17  
**Plan step:** Phase 19.6  
**Status:** Complete  
**Previous handoff:** `0138-production-application-fabric-and-console.md`

## Scope completed

- Added an owner-private daemon-managed MCP ingress Unix endpoint.
- Added strict bounded versioned framing for bootstrap, session, tool discovery,
  invocation, result, and safe error messages.
- Added mode-0600 `mcp-ingress.json` configuration with explicit enabled state,
  client identities, capability allowlists, and bounded session lifetimes.
- Persisted expiring client authority through the production Core repository.
- Reused one-time token authentication for the second session connection; raw
  bootstrap credentials are never persisted and cannot be reused.
- Composed `LifecycleCoreIngressGateway` with durable authority lookup, durable
  replay protection, schema validation, and final-result enforcement.
- Added a production MCP executor that delegates only non-application tasks to
  `ProductionTaskGateway`. The authenticated client principal and session are
  retained in the delegated Core authority rather than replaced by
  `local-owner`.
- Exposed `fam.ask` and fail-closed `fam.ask.verified`. The latter releases no
  model content unless normal Core verification succeeds.
- Added `fam-os --prefix ... mcp serve --client-id ...`, which speaks official
  MCP SDK stdio while leaving all authority and execution in the daemon.
- Moved runtime catalog selection and small parsing/routing helpers into focused
  modules so the product service, gateway, and application worker remain below
  the repository's 300-line module target.

## Security boundary

The stdio bridge cannot call Ollama, application connectors, or Core storage.
The daemon validates Unix peer UID, consumes a one-time token, and rechecks the
durable allowlist on every discovery and call. Generic MCP tools cannot acquire
application context or mutation authority. Same-user hostile-process isolation
is not claimed; that wider Linux session boundary also has access to the
owner's Shell endpoint and remains an explicit security-review concern.

## Validation

- The complete repository suite passes: 916 tests, two declared skips.
- End-to-end tests start the real product service, connect through the private
  socket, prove permission-filtered discovery, complete a durable Core request,
  and confirm the delegated authority retains the configured client principal.
- A second end-to-end test launches the installed CLI command shape as an
  official MCP SDK stdio subprocess, initializes it, lists tools, and calls FAM.
- A verification-required MCP call proves unverified model content is withheld.
- Unknown clients, non-private configuration, unknown fields, and unknown
  capabilities fail closed.
- Ruff passes for the changed production and test modules.
- Mypy passes for the 14 affected source modules.
- The MCP architecture boundary test proves ingress does not import model,
  connector, application, registry, scheduler, supervisor, or memory bypass
  layers.

## Next entry point

Implement Phase 19.7 as an explicit production fallback-policy composition.
Accessibility and screen/input must remain disabled by default; enabling either
must expose its observation scope, action primitives, confirmation behavior,
and privacy impact to Console and Core. Do not silently activate an adapter
merely because the desktop supports it.
