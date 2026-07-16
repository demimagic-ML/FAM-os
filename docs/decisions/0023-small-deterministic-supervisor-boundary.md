# ADR 0023: Keep the Supervisor a typed user-session enforcement boundary

**Status:** Accepted  
**Date:** 2026-07-16

## Context

FAM_OS already has provider-neutral lifecycle/resource contracts plus user-systemd and cgroup adapters migrated for parity. Phase 3 could mistakenly turn these mechanics into a broad privileged daemon or place model readiness, scheduling, and application policy inside the supervisor.

## Decision

Define a typed `SupervisorBoundary` that separates implemented, planned, and prohibited responsibilities.

Implemented capability is limited to owned unprivileged user-session service start/stop/status, declared service resource limits, and owned resource observation. Device/filesystem grants, immutable audit emission, and recovery remain planned until their dedicated steps implement and test them.

Production admission requires an authenticated caller and explicit user-session ownership scope. Current direct in-process adapter composition is not an external authorization API.

System-service administration and model logic are structurally prohibited. The supervisor also excludes prompt interpretation, routing/planning, memory, content verification, application decisions, arbitrary process control, secrets, and installation.

## Consequences

- Phase 3 can reconcile existing mechanics without granting new privilege.
- Core and model behavior cannot leak into the trusted enforcement boundary.
- Planned capabilities cannot be mistaken for implemented authority.
- A future helper may be added only for a specific capability and cannot become a general root daemon.
- Authentication and ownership still require concrete Phase 3 contracts and tests before an external caller exists.

## Alternatives considered

1. Put the Supervisor in the Linux kernel: rejected because lifecycle policy and AI coordination do not belong in kernel space.
2. Run all supervisor operations as root: rejected because current capability works user-scoped and least privilege is mandatory.
3. Treat systemd unit names as authorization: rejected because naming is not ownership proof.
4. Move model readiness and eviction into Supervisor: rejected because those are runtime/scheduler use-case concerns.
5. Document non-goals only in prose: rejected because typed invariants are testable and discoverable by implementation code.

## Evidence

- `src/fam_os/supervisor/boundary.py`
- `tests/unit/test_supervisor_boundary.py`
- `docs/architecture/SUPERVISOR_BOUNDARY.md`
- Existing ADR 0006 user-systemd/cgroup boundary
