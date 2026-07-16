# Handoff 0024: Verified applied cgroup resource limits

**Date:** 2026-07-16  
**Plan step:** Phase 3.3  
**Status:** Complete  
**Previous handoff:** `0023-owned-service-lifecycle.md`

## Objective

Require live applied-state proof for requested CPU, memory, swap, and process ceilings before an owned user service can be reported as constrained, with compensating cleanup when proof is missing or mismatched.

## Scope completed

- Added provider-neutral CPU-quota and count ceilings with explicit finite/unbounded semantics.
- Extended `ResourceSnapshot` with applied CPU quota, current task count, and task ceiling.
- Added pure parsers for `cpu.max`, `pids.current`, and `pids.max`.
- Extended the cgroup-v2 observer and parity serialization with CPU-quota/task evidence.
- Added exact `AppliedLimitCheck` results for memory, swap, CPU quota, and task count.
- Distinguished matched, mismatched, unavailable, and not-requested evidence.
- Preserved the semantic difference between a missing controller field and an explicit `max` ceiling.
- Required at least one requested/matched ceiling before an outcome can claim constrained execution.
- Added `ConstrainedServiceLifecycle` above owned lifecycle and resource observation.
- Required explicit `APPLY_SERVICE_RESOURCE_LIMITS` authority before start.
- Performed a compensating raw-adapter stop for the just-started owned service when applied verification failed.
- Added fake-driven exact/mismatch/unavailable/unbounded/rollback tests.
- Ran a live constrained user-service smoke with exact 64 MiB RAM, zero swap, 25% CPU, and eight-task ceilings.
- Proved post-test unit removal.
- Added architecture documentation, ADR 0025, Master Plan status, and this handoff.

## Explicitly not completed

- No direct cgroup write was added; systemd remains the controller owner.
- No storage-I/O, device, filesystem, GPU, thermal, or power enforcement was added.
- No retry, delayed reconciliation, durable desired-state store, or general recovery loop was added.
- No external authenticator or transport was added.
- The compensating stop is scoped to failed admission; Phase 3.6 still owns crash recovery and safe termination policy.

## Architecture and decisions

ADR 0025 rejects systemd command success as enforcement proof. `ResourceLimits` is requested intent, `ResourceSnapshot` is observed state, and `AppliedLimitsVerification` is the deterministic comparison.

An observed `ResourceCeiling(None)`, `CpuQuotaCeiling(None)`, or `CountCeiling(None)` is explicitly unbounded and therefore mismatched when the caller requested a finite bound. A missing snapshot/field is unavailable. Neither passes.

Limits not requested by a service are marked `not_requested`, which supports profiles without artificial memory/CPU caps. However an all-unrequested definition cannot call itself constrained.

Rollback bypasses caller stop authorization only for the exact service whose admitted start just failed applied-limit verification. It is compensating cleanup, not general unit-control authority.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/supervisor/contracts.py` | CPU quota/count ceilings and snapshot fields |
| `src/fam_os/supervisor/limit_verification.py` | Exact requested-versus-applied checks |
| `src/fam_os/supervisor/constrained.py` | Constrained start and compensating cleanup |
| `src/fam_os/supervisor/__init__.py` | Public exports |
| `src/fam_os/adapters/cgroup/parsing.py` | CPU quota and PID ceiling parsers |
| `src/fam_os/adapters/cgroup/observer.py` | Applied CPU/PID observation |
| `tools/parity/serialization.py` | New measurement fields in reports |
| `tests/fixtures/cgroup/.../cpu.max` | CPU quota fixture |
| `tests/fixtures/cgroup/.../pids.current` | Current task fixture |
| `tests/fixtures/cgroup/.../pids.max` | Task ceiling fixture |
| `tests/unit/test_applied_resource_limits.py` | Match, mismatch, unavailable, and unbounded tests |
| `tests/unit/test_constrained_service_lifecycle.py` | Admission, rollback, and authority tests |
| `tests/unit/test_cgroup_parsing.py` | New parser coverage |
| `tests/unit/test_cgroup_observer.py` | New observation coverage |
| `tests/hardware/constrained_service_smoke.py` | Opt-in exact live cgroup proof |
| `docs/architecture/APPLIED_RESOURCE_LIMITS.md` | Verification protocol |
| `docs/decisions/0025-verify-applied-cgroup-limits.md` | Applied-state decision |

## Public interfaces

- `CpuQuotaCeiling`
- `CountCeiling`
- `LimitVerificationStatus`
- `AppliedLimitCheck`
- `AppliedLimitsVerification`
- `verify_applied_limits`
- `ConstrainedStartOutcome`
- `ConstrainedServiceLifecycle`

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_applied_resource_limits \
  tests.unit.test_constrained_service_lifecycle \
  tests.unit.test_cgroup_parsing \
  tests.unit.test_cgroup_observer \
  tests.unit.test_systemd_commands
```

Result: all 18 focused tests passed in 0.001 seconds; 0 failures.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
```

Result: all 274 FAM_OS tests passed in 0.195 seconds; 0 failures. The previous suite contained 267 tests.

```bash
FAM_CONSTRAINED_SERVICE_SMOKE=1 PYTHONPATH=src:. \
  python3 -m unittest tests.hardware.constrained_service_smoke -v
```

Result: one live test passed in 0.071 seconds. It observed all four exact ceilings. Post-cleanup state was `LoadState=not-found`, `ActiveState=inactive`, `SubState=dead`.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
python3 -m compileall -q src tools tests
```

Result: 35 generated schemas matched and compilation completed successfully.

An AST audit found no implementation module at or above 300 lines and no function at or above 50 lines.

## Known limitations and risks

- Exact floating CPU comparison uses a 0.001 percentage-point tolerance.
- Verification is a point-in-time read after start; later external limit drift is not yet monitored.
- A failed compensating stop exception can still escape; Phase 3.6 must formalize termination escalation and evidence.
- `pids.current` is observed but not part of ceiling equality, only `pids.max` is.
- Full-host profiles that request only zero swap can satisfy constrained admission from that single matched ceiling; Scheduler admission remains responsible for the overall budget.
- No storage bandwidth/IOPS cgroup policy is represented in `ResourceLimits` yet.

## Operational notes

The only live mutation was a temporary user-scoped `/usr/bin/sleep 20` service named `fam-phase33-smoke`. Systemd applied a 64 MiB memory ceiling, zero swap, 25% CPU quota, and eight-task ceiling. Cleanup removed the unit. No model, system service, persistent configuration, or existing application changed.

## Recommended next entry point

Begin Phase 3.4. Define provider-neutral, allowlisted device and filesystem grant contracts scoped to principal, session, owned service, access mode, exact resource identity, issue/expiry, and revocation. Reject raw arbitrary paths and device strings at the domain boundary before introducing Linux-specific adapters.
