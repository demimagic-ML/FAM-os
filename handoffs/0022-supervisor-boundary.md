# Handoff 0022: Typed FAM Supervisor capability boundary

**Date:** 2026-07-16  
**Plan step:** Phase 3.1  
**Status:** Complete  
**Previous handoff:** `0021-full-workstation-smoke-baseline.md`

## Objective

Define the smallest deterministic FAM Supervisor boundary before expanding enforcement, separating capabilities already proven by user-systemd/cgroup adapters from planned Phase 3 work and from authority that the supervisor must never acquire.

## Scope completed

- Added the versioned source-level `fam.supervisor.boundary/v1alpha1` contract.
- Added an explicit user-session trust scope.
- Declared five current capabilities: start an unprivileged service, stop an owned service, read owned status, apply service resource limits, and observe owned resources.
- Declared four planned capabilities without reporting them as implemented: device grant, filesystem grant, immutable audit emission, and failed-service recovery.
- Declared explicit non-goals for inference, prompts, routing/planning, memory, verification, application decisions, arbitrary process control, system-service administration, secrets, and installation.
- Required an authenticated caller and prohibited enabling system-service control or model logic through boundary data.
- Required current and planned capability sets to remain non-empty, unique, and disjoint.
- Added `canonical_supervisor_boundary()` as the single current declaration.
- Added tests proving current/planned distinction and prohibited authority invariants.
- Added architecture documentation, ADR 0023, ownership guidance, Master Plan status, and this handoff.

## Explicitly not completed

- No external supervisor API, socket, daemon, or authenticated transport was added.
- No caller identity, ownership token, or authorization implementation was added; that enters Phase 3.2/3.4 through explicit ports.
- No root helper, system service, polkit rule, Linux capability, device rule, filesystem grant, audit log, recovery loop, or threat-model test was added.
- Existing user-systemd/cgroup adapter behavior was not reclassified as a production authorization boundary.

## Architecture and decisions

ADR 0023 keeps the Supervisor above the Linux kernel and below FAM Core. Core supplies already-selected intent; the Supervisor validates deterministic enforcement language and delegates it to replaceable OS adapters.

Current capability is user-session scoped because existing mechanics need no root authority. A future helper is allowed only if a specific later capability cannot be implemented safely in user scope; it cannot become a general systemd or process-control daemon.

`planned_capabilities` is deliberately distinct from `implemented_capabilities`. Code must use `implements()` before claiming authority. Documentation or a roadmap entry never grants runtime permission.

Authentication is an invariant but not an implementation claim. Current development tools compose adapters directly in-process; Phase 3 must introduce a caller/ownership boundary before any external interface.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/supervisor/boundary.py` | Capability, trust-scope, non-goal, and canonical-boundary contracts |
| `src/fam_os/supervisor/__init__.py` | Public boundary exports |
| `src/fam_os/supervisor/README.md` | Package ownership and next authorization requirement |
| `tests/unit/test_supervisor_boundary.py` | Boundary invariant and capability tests |
| `docs/architecture/SUPERVISOR_BOUNDARY.md` | Capability, caller, ownership, privilege, and non-goal model |
| `docs/decisions/0023-small-deterministic-supervisor-boundary.md` | Boundary decision |
| `README.md` | Current implementation status |
| `MASTER_PLAN.md` | Phase 3.1 completion and Phase 3.2 entry point |
| `handoffs/README.md` | Handoff sequence entry |
| `handoffs/0022-supervisor-boundary.md` | This record |

## Public interfaces

- `SUPERVISOR_BOUNDARY_CONTRACT_VERSION`
- `SupervisorTrustScope`
- `SupervisorCapability`
- `SupervisorNonGoal`
- `SupervisorBoundary`
- `SupervisorBoundary.implements()`
- `canonical_supervisor_boundary()`

These are Python source contracts. They are not an external authorization format and were not added to the Phase 2 serialized schema catalog.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_supervisor_boundary \
  tests.unit.test_supervisor_contracts \
  tests.unit.test_systemd_commands \
  tests.unit.test_systemd_lifecycle \
  tests.unit.test_cgroup_observer
```

Result: all 19 focused tests passed in 0.001 seconds; 0 failures.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
```

Result: all 261 FAM_OS tests passed in 0.192 seconds; 0 failures. The previous suite contained 257 tests.

```bash
python3 -m compileall -q src tools tests
```

Result: completed successfully.

## Known limitations and risks

- The boundary states authentication and ownership requirements but cannot enforce them until concrete Phase 3 ports and orchestration exist.
- `ServiceLifecycle` still accepts a service ID for stop/status without caller context; Phase 3.2 must wrap it rather than exposing it directly.
- Environment values remain command arguments in the current systemd adapter and must not carry secrets.
- Service-definition command paths are not yet allowlisted by a package/capability registry.
- User-systemd ownership is process/session mechanics, not FAM principal ownership.
- No device or filesystem capability vocabulary exists yet beyond the planned high-level capability names.

## Operational notes

This step added pure contracts, tests, and documentation. It performed no service start, stop, system mutation, hardware probe, model inference, or external application action.

## Recommended next entry point

Begin Phase 3.2. Introduce an ownership-aware supervisor use case above `ServiceLifecycle`, with an injected caller authenticator/authority port and a registry of FAM-owned service definitions. Define idempotent start/stop/status behavior and reject service IDs outside caller scope. Reuse the user-systemd adapter unchanged behind the port until tests prove a concrete adapter change is required.
