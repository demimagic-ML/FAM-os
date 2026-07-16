# Handoff 0023: Ownership-aware unprivileged service lifecycle

**Date:** 2026-07-16  
**Plan step:** Phase 3.2  
**Status:** Complete  
**Previous handoff:** `0022-supervisor-boundary.md`

## Objective

Turn the existing unprivileged lifecycle mechanism into deterministic supervisor behavior by requiring injected authorization, explicit principal/session ownership, exact service-definition claims, independent FAM namespace enforcement, and idempotent start/stop/status operations.

## Scope completed

- Added `SupervisorCallContext` with request, principal, session, and opaque authority references; it contains no secret or self-attested authentication boolean.
- Added the injected `SupervisorAuthorizer` port.
- Added immutable `OwnedService` declarations.
- Added the replaceable `ServiceOwnershipRegistry` port and deterministic in-memory implementation.
- Required exact principal/session and `ServiceDefinition` equality for repeated claims.
- Rejected cross-owner service access and same-ID definition changes.
- Enforced the `fam-` service namespace inside the registry independently of authorization.
- Added `OwnedServiceLifecycle` above the existing provider-neutral lifecycle port.
- Made active/activating start idempotent and rejected start during deactivation.
- Made inactive/unknown/deactivating stop idempotent.
- Required authorization and ownership before status or stop reaches the adapter.
- Added stable authorization, ownership, and definition-conflict errors.
- Added six fake-driven tests and one opt-in live user-systemd smoke.
- Proved the live temporary service was removed after cleanup.
- Added architecture documentation, ADR 0024, Master Plan status, and this handoff.

## Explicitly not completed

- No external authentication implementation, local transport, token format, or credential storage was added.
- No durable ownership registry or restart reconciliation was added.
- No system service, root helper, arbitrary process control, persistent unit, boot enablement, or daemon reload was added.
- No model readiness, scheduling, resource-policy selection, audit emission, or recovery loop was placed in lifecycle orchestration.
- Phase 3.3 still owns requested-versus-applied resource-budget verification.

## Architecture and decisions

ADR 0024 places ownership above the OS adapter because authorization and principal scope must remain provider-neutral. The systemd adapter continues to translate already-admitted lifecycle intent only.

Namespace and principal ownership are separate checks. `fam-` prevents general unit scope; the registry prevents one FAM caller from controlling another caller's service. Both are required.

Definition equality is part of idempotence. A repeated start with different command, environment, or limits is a conflict, not an update. Future updates require an explicit audited transition.

The in-memory registry proves semantics without choosing persistence. `ServiceOwnershipRegistry` allows a durable adapter later, but any replacement must preserve claim and `require_owned` behavior.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/supervisor/access.py` | Call context and authorizer port |
| `src/fam_os/supervisor/ownership.py` | Owned service, registry port, namespace and claim policy |
| `src/fam_os/supervisor/lifecycle.py` | Ownership-aware idempotent lifecycle use case |
| `src/fam_os/supervisor/errors.py` | Authorization, ownership, and definition-conflict errors |
| `src/fam_os/supervisor/__init__.py` | Public exports |
| `tests/unit/test_owned_service_lifecycle.py` | Authorization, ownership, namespace, conflict, and idempotence tests |
| `tests/hardware/owned_service_lifecycle_smoke.py` | Opt-in live wrapper smoke |
| `docs/architecture/OWNED_SERVICE_LIFECYCLE.md` | Admission, ownership, and idempotence protocol |
| `docs/decisions/0024-owned-unprivileged-service-lifecycle.md` | Lifecycle ownership decision |
| `src/fam_os/supervisor/README.md` | Package status |
| `README.md`, `MASTER_PLAN.md`, `handoffs/README.md` | Project status and history |

## Public interfaces

- `SupervisorCallContext`
- `SupervisorAuthorizer`
- `OwnedService`
- `ServiceOwnershipRegistry`
- `InMemoryServiceOwnershipRegistry`
- `OwnedServiceLifecycle`
- `SupervisorAuthorizationError`
- `ServiceOwnershipError`
- `ServiceDefinitionConflictError`

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_owned_service_lifecycle \
  tests.unit.test_supervisor_boundary \
  tests.unit.test_systemd_lifecycle
```

Result: all 13 focused tests passed in 0.001 seconds; 0 failures.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
```

Result: all 267 FAM_OS tests passed in 0.194 seconds; 0 failures. The previous suite contained 261 tests.

```bash
FAM_OWNED_LIFECYCLE_SMOKE=1 PYTHONPATH=src:. \
  python3 -m unittest tests.hardware.owned_service_lifecycle_smoke -v
```

Result: one live test passed in 0.034 seconds. Post-cleanup systemd state was `LoadState=not-found`, `ActiveState=inactive`, `SubState=dead`.

```bash
python3 -m compileall -q src tools tests
```

Result: completed successfully.

## Known limitations and risks

- The authorizer is a port only; no production authenticator exists yet.
- In-memory ownership is lost on process restart.
- `UNKNOWN` stop is treated as idempotently absent for a registry-owned service; recovery reconciliation must distinguish an absent unit from an observation failure.
- Exact-definition conflict prevents implicit updates but no explicit update transition exists yet.
- Service environment remains part of the definition and must not contain secrets.
- Command executable allowlisting still depends on future package/capability policy.
- The benchmark tool still composes the raw lifecycle adapter directly; production migration should use the owned wrapper when caller/registry composition exists.

## Operational notes

The only live mutation was a temporary user-scoped `/usr/bin/sleep 20` transient service named `fam-phase32-smoke`. Cleanup ran in `finally`, and the unit was removed. No system service, model, hardware setting, existing application, or persistent configuration changed.

## Recommended next entry point

Begin Phase 3.3. Add provider-neutral applied-limit evidence for CPU quota, tasks maximum/current, memory, and swap. Compose a constrained owned-service start that observes the live cgroup and refuses to report constrained success when requested ceilings are absent or different. Keep systemd property construction and cgroup parsing in their existing adapters.
