# Handoff 0028: Verified failed-service recovery and safe termination

**Date:** 2026-07-16  
**Plan step:** Phase 3.6 failure recovery and safe service termination  
**Status:** Complete  
**Previous handoff:** `0027-immutable-supervisor-audit.md`

## Objective

Return failed or deliberately terminated owned services to a verified inactive
baseline, retire their old access grants, preserve required audit linkage, and
keep restart/retry policy outside the deterministic Supervisor.

## Scope completed

- Added immutable termination reason, disposition, and report contracts.
- Added dedicated failed-recovery and safe-termination capabilities.
- Added `ServiceRecoveryController` with ownership, dedicated authority, known-
  state admission, pre-stop resource evidence, stop, final-state verification,
  deterministic grant revocation, and required audit outcomes.
- Defined recovery as failed-to-inactive cleanup; it never restarts a service.
- Rejected `UNKNOWN`, nonfailed recovery input, noninactive final state, retained
  final PID, cross-service evidence, and unordered/duplicate grant evidence.
- Added stable enumeration of every unrevoked grant for one service.
- Revoked grants in grant-ID order through the existing audited access controller.
- Added a provider-neutral `ServiceFailureReset` port.
- Implemented systemd failed-state reset using `systemctl --user reset-failed`.
- Added explicit `retain_failed_state=True` mapping to
  `CollectMode=inactive`; default transient collection remains unchanged.
- Moved recovery and safe termination to implemented boundary capabilities; the
  Phase 3 boundary now has no planned-but-unimplemented capability.
- Added unit and live hardware tests, architecture documentation, ADR 0029, and
  this handoff.

## Explicitly not completed

- Recovery does not restart, reroute, regrant, or choose a retry budget.
- The Supervisor does not diagnose model output or decide whether a workload is
  semantically healthy.
- A grant cleanup failure returns no successful termination report; the service
  remains inactive and reconciliation is required before restart.
- Durable recovery state/registries and external authenticated transport remain
  future work.
- Multi-user recovery, packaging, retention, and long-running crash tests remain
  Phase 14 work.
- The Supervisor threat model and adversarial security suite are Phase 3.7.

## Architecture and decisions

ADR 0029 chooses a safe inactive baseline over automatic restart. This keeps
failure cleanup deterministic and prevents stale authority from flowing into a
new process. Core must perform a new admitted start with new resource and access
decisions if it wants to retry.

The first live smoke deliberately failed: a fast transient service started with
`--collect` was garbage-collected to `inactive` before recovery could observe
`failed`. Retaining failure exposed a second systemd fact: `stop` alone left the
unit failed. The final adapter uses `CollectMode=inactive` when explicitly
requested, then issues `reset-failed` after stop. The live rerun observed failed
and ended inactive with no PID.

Unknown status is not equated with absence. A successful typed report can only be
constructed from exact inactive final evidence.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/supervisor/recovery_contracts.py` | Immutable termination evidence |
| `src/fam_os/supervisor/recovery.py` | Audited recovery/termination workflow |
| `src/fam_os/supervisor/ports/recovery.py` | Provider-neutral failed reset port |
| `src/fam_os/supervisor/access_registry.py` | Stable per-service unrevoked grants |
| `src/fam_os/supervisor/errors.py` | Stable recovery error |
| `src/fam_os/supervisor/audit_outcomes.py` | Bounded incomplete-recovery code |
| `src/fam_os/supervisor/boundary.py` | Recovery/termination capabilities implemented |
| `src/fam_os/adapters/systemd/settings.py` | Explicit failure retention policy |
| `src/fam_os/adapters/systemd/commands.py` | CollectMode and reset-failed commands |
| `src/fam_os/adapters/systemd/lifecycle.py` | Failed-state reset implementation |
| `tests/unit/test_service_recovery.py` | Workflow, denial, audit, state, grant tests |
| `tests/unit/test_systemd_commands.py` | Retention/reset command tests |
| `tests/hardware/service_recovery_smoke.py` | Real exit-code failure recovery proof |
| `docs/architecture/SAFE_SERVICE_RECOVERY.md` | Recovery invariants and boundaries |
| `docs/decisions/0029-verified-inactive-service-recovery.md` | Recovery decision |

## Public interfaces

- `ServiceTerminationReason`
- `ServiceTerminationDisposition`
- `ServiceTerminationReport`
- `ServiceRecoveryController.terminate(...)`
- `ServiceRecoveryController.recover_failed(...)`
- `ServiceFailureReset.reset_failed(...)`
- `InMemoryAccessGrantRegistry.unrevoked_for_service(...)`
- `SystemdUserSettings.retain_failed_state`
- `SystemdUserServiceLifecycle.reset_failed(...)`
- `SupervisorCapability.RECOVER_FAILED_SERVICE`
- `SupervisorCapability.SAFE_TERMINATE_OWNED_SERVICE`

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_systemd_commands \
  tests.unit.test_systemd_lifecycle \
  tests.unit.test_service_recovery \
  tests.unit.test_supervisor_boundary
```

Result: all 22 focused tests passed.

```bash
FAM_SERVICE_RECOVERY_SMOKE=1 PYTHONPATH=src:. \
  python3 -m unittest tests.hardware.service_recovery_smoke -v
```

Result: the real failed transient user-service smoke passed in 0.156 seconds. It
observed exit-code failure, stopped and reset the exact owned unit, verified
inactive/no-PID state, verified two linked audit records, and verified ledger
mode `0600`.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
python3 -m compileall -q src tools tests
```

Result: all 323 tests passed in 0.252 seconds, all 35 generated schemas matched,
and compilation completed successfully. Phase 3.5 closed with 313 tests.

An AST audit found no `src/` or `tools/` module at or above 300 lines and no
function at or above 50 lines.

Larry refreshed 467 files and verified clean. The codebase graph refreshed in
fast mode with 6,987 nodes and 21,238 edges.

## Known limitations and risks

- A failed access-adapter or required-audit write during grant cleanup leaves no
  successful report; callers must not restart until reconciliation completes.
- The in-memory ownership and grant registries are not crash-durable yet.
- `retain_failed_state` must be selected before launch when failure diagnostics
  are required; the default still favors automatic collection.
- Resource evidence may be unavailable after a cgroup has already disappeared;
  final service state/no-PID evidence remains mandatory.
- Advisory audit locking and local hash-chain rollback limitations from Phase 3.5
  still apply.
- Phase 3.7 must explicitly test attempts to bypass the audited/recovery
  compositions and address arbitrary process/system-service control threats.

## Recommended next entry point

Begin Phase 3.7 by inventorying trust boundaries and attacker capabilities across
caller context, service IDs/definitions, grant IDs/resources, Bubblewrap paths,
systemd commands, cgroup observations, audit files, and recovery state. Convert
each threat into an executable negative/security test, then run one combined live
dummy-service start/constrain/observe/access/audit/terminate proof to close the
Phase 3 exit gate.
