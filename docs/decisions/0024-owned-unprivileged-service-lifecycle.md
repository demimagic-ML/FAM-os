# ADR 0024: Authorize and claim FAM-owned services above the OS adapter

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The migrated `ServiceLifecycle` port and systemd adapter accept raw service IDs. That is appropriate for an OS mechanism but insufficient for a supervisor boundary: exposing it directly would allow arbitrary unit probing/control and would make duplicate start/stop behavior adapter-dependent.

## Decision

Add `OwnedServiceLifecycle` above `ServiceLifecycle`. Every operation requires an injected `SupervisorAuthorizer` and an explicit `SupervisorCallContext`. Service start then claims the exact definition for one principal/session in a `ServiceOwnershipRegistry`; status and stop require that same ownership.

Restrict registry claims and lookups to `fam-` service IDs independently of authorization. Reject cross-owner claims and definition changes. Make already-active start and already-stopped stop deterministic and idempotent before calling the adapter.

Keep the user-systemd adapter unchanged. Authentication, registry persistence, and transports remain replaceable ports or later adapter work.

## Consequences

- Raw OS unit names are no longer the supervisor's ownership model.
- An authorizer error cannot grant arbitrary systemd-unit scope outside `fam-`.
- Duplicate lifecycle requests do not repeat mutations.
- Restart with changed intent requires an explicit future transition rather than silently replacing a definition.
- The in-memory registry is not durable across process restart; Phase 3 recovery must reconcile persisted declarations and OS state.

## Alternatives considered

1. Add ownership checks inside the systemd adapter: rejected because ownership is provider-neutral policy.
2. Trust an `authenticated=True` field from callers: rejected because callers cannot attest themselves.
3. Use the unit-name prefix only: rejected because namespace is not principal ownership.
4. Let start replace an existing definition: rejected because hidden command/limit changes are not idempotent.
5. Implement a durable database immediately: rejected because Phase 3.2 first needs pure semantics and an injectable registry boundary.

## Evidence

- `src/fam_os/supervisor/access.py`
- `src/fam_os/supervisor/ownership.py`
- `src/fam_os/supervisor/lifecycle.py`
- `tests/unit/test_owned_service_lifecycle.py`
- `tests/hardware/owned_service_lifecycle_smoke.py`
- `docs/architecture/OWNED_SERVICE_LIFECYCLE.md`
