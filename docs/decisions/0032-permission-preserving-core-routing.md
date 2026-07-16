# ADR 0032: Route only admitted requests and preserve exact permission scope

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The existing `TaskRouter` and routing contracts were provider-neutral, but Core
had no generic lifecycle between admission and routing. Calling the router with a
raw task would bypass authority binding. Passing the complete permission context
would disclose identity and excess capability scope, while accepting a modified
capability list from the router could widen or silently drop requirements.

Provider exceptions and malformed results also need structured handling before a
generic plan state machine can consume routing evidence.

## Decision

Accept only `AdmittedTaskRequest` in `CoreRoutingService`. Recheck permission
expiry before routing. Construct a `RoutingRequest` containing only request ID,
prompt, and exact effective capabilities.

Call the provider-neutral `TaskRouter` port and bind a valid `RoutingResult` back
to the admitted request. Require exact ordered equality between route-declared
and effective capabilities. Map router exceptions and incompatible evidence to
fixed structured failures without raw details.

Tighten routing contract version, identity, prompt, capability, confidence, and
reason bounds. Keep the lifecycle independent from the model router implementation
and all external/runtime boundaries.

## Consequences

- Raw tasks cannot use the generic routing lifecycle.
- Routers receive prompt and capability needs but no identity/credential context.
- Route evidence cannot widen, drop, substitute, or reorder effective authority.
- Permission expiry prevents a stale admitted request from reaching the router.
- Provider failures are safe, typed, and non-releasing.
- Model-backed and deterministic routers remain interchangeable behind one port.
- Plan construction and retry policy remain later Phase 4 work.

## Alternatives considered

1. Route raw `TaskRequest`: rejected because it bypasses admission.
2. Pass full permission/authority context: rejected as unnecessary identity and
   privilege disclosure.
3. Allow router capability supersets: rejected because classification must not
   grant authority.
4. Allow router capability subsets: rejected because requirements could silently
   disappear before planning.
5. Propagate provider exceptions: rejected because final Core failures must be
   bounded and provider-neutral.

## Evidence

- `src/fam_os/core/routing/contracts.py`
- `src/fam_os/core/routing/service.py`
- `src/fam_os/routing/contracts.py`
- `tests/unit/test_core_routing_lifecycle.py`
- `tests/architecture/test_core_routing_boundary.py`
