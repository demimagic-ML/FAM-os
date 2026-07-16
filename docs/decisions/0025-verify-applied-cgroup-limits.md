# ADR 0025: Verify applied cgroup limits before claiming constrained execution

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The systemd command builder already requests memory, swap, CPU, and task ceilings, but successful command execution only proves that systemd accepted a start request. Missing controllers, property translation changes, or configuration drift could leave a service less constrained than declared.

## Decision

Extend provider-neutral resource snapshots with observed CPU-quota and task ceilings. Parse `cpu.max`, `pids.current`, and `pids.max` in the cgroup adapter.

Add exact requested-versus-applied verification with separate matched, mismatched, unavailable, and not-requested states. Preserve the difference between a missing field and explicit `max`.

Add `ConstrainedServiceLifecycle` above owned lifecycle and resource observation. A start is constrained only when every requested ceiling matches. Otherwise perform a compensating stop and return a non-constrained outcome containing the evidence and cleanup status.

## Consequences

- Command construction is no longer treated as enforcement proof.
- CPU, RAM, swap, and PID budgets share one verification policy.
- A missing controller or unbounded applied ceiling fails closed.
- Full-host services may leave a resource unrequested, but at least one requested limit must match to claim constrained execution.
- Rollback is bounded to the just-admitted owned service; broader recovery remains separate.

## Alternatives considered

1. Trust `systemd-run` exit status: rejected because acceptance is not applied-state evidence.
2. Write cgroup files directly: rejected because that conflicts with systemd ownership.
3. Treat missing values as unbounded: rejected because unknown and explicit `max` differ.
4. Log mismatches but keep services running: rejected because a safety ceiling is not advisory.
5. Put comparison in the systemd adapter: rejected because requested-versus-applied policy is provider-neutral Supervisor behavior.

## Evidence

- `src/fam_os/supervisor/limit_verification.py`
- `src/fam_os/supervisor/constrained.py`
- `src/fam_os/adapters/cgroup/parsing.py`
- `src/fam_os/adapters/cgroup/observer.py`
- `tests/unit/test_applied_resource_limits.py`
- `tests/unit/test_constrained_service_lifecycle.py`
- `tests/hardware/constrained_service_smoke.py`
