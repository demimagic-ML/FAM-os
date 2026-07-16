# Handoff 0006: Systemd and cgroup supervisor adapters

**Date:** 2026-07-16  
**Plan step:** Phase 1.7  
**Status:** Complete  
**Previous handoff:** `0005-ollama-inference-adapter.md`

## Objective

Move the prototype's user-systemd service lifecycle, resource enforcement, and cgroup-v2 observation behind deterministic provider-neutral supervisor contracts without copying its model-specific god script, readiness polling, scheduling policy, or report coupling.

## Scope completed

- Added immutable supervisor contracts for service definitions, lifecycle state, status, resource limits, finite or unbounded ceilings, resource events, pressure samples, and complete snapshots.
- Added provider-neutral `ServiceLifecycle` and `ResourceObserver` ports.
- Added stable supervisor errors for lifecycle and malformed resource-controller failures.
- Added a user-scoped systemd lifecycle adapter with explicit command and timeout settings.
- Added pure command builders for transient start, stop, and status operations.
- Preserved the prototype's memory and no-swap enforcement and added typed CPU-quota and task-count properties supported by the same systemd boundary.
- Forced every Phase 1 lifecycle operation through `systemd-run --user` or `systemctl --user`, without a shell.
- Added a read-only cgroup-v2 observer for memory current, peak, ceiling, swap, memory events, and pressure-stall information.
- Distinguished a missing limit from an explicit cgroup `max` ceiling.
- Separated generic service lifecycle from application-specific readiness polling.
- Added synthetic systemd and cgroup fixtures plus 19 focused tests, increasing the FAM_OS suite from 38 to 57 tests.
- Started, observed, and stopped one short-lived bounded dummy service through the real adapters.

## Explicitly not completed

- No system service or privileged daemon was installed.
- No direct cgroup-controller file mutation was added; systemd owns transient service cgroups and applies approved properties.
- No root-scoped lifecycle command, polkit authorization, privilege separation, capability grant, namespace policy, seccomp policy, or device permission was added.
- No durable unit-file creation, daemon reload, enablement, boot persistence, or service recovery was added.
- No application readiness or Ollama endpoint polling was placed in the generic lifecycle adapter.
- No scheduling, admission, eviction, routing, model, prompt, or verification policy was added.
- No immutable audit-event emission or production supervisor API was added; these remain Phase 3 work.
- The parent `scripts/rnf-cpu-server` remains unchanged as prototype evidence until Phase 1 parity is complete.

## Architecture and decisions

ADR 0006 establishes three independent layers:

1. `supervisor` owns deterministic service and resource language.
2. `adapters/systemd` owns user-systemd commands and status mapping.
3. `adapters/cgroup` owns read-only cgroup-v2 path resolution and controller parsing.

`SystemdUserServiceLifecycle` implements the supervisor lifecycle port and also provides the resource-group locator consumed structurally by `CgroupV2ResourceObserver`. The public supervisor contract calls that value an opaque resource group; it does not expose systemd property dictionaries or require Core to understand cgroup paths.

`ResourceSnapshot.memory_limit is None` means that no ceiling observation was available. `ResourceCeiling(None)` means the controller explicitly reported `max`. This distinction is required so future admission policy cannot mistake unknown capacity for unlimited capacity.

Generic lifecycle success means the operating-system service was created, not that an application protocol is ready. Model or application health checks must be bounded use-case behavior layered above this port.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/supervisor/contracts.py` | Provider-neutral service, limit, event, pressure, and snapshot contracts |
| `src/fam_os/supervisor/errors.py` | Stable lifecycle and observation errors |
| `src/fam_os/supervisor/ports/lifecycle.py` | Start, stop, and status port |
| `src/fam_os/supervisor/ports/resources.py` | Read-only service resource-observation port |
| `src/fam_os/supervisor/__init__.py`, `ports/__init__.py` | Public supervisor exports |
| `src/fam_os/adapters/systemd/settings.py` | Explicit command and timeout settings |
| `src/fam_os/adapters/systemd/commands.py` | Pure user-systemd command construction |
| `src/fam_os/adapters/systemd/parsing.py` | Systemd property and lifecycle-state conversion |
| `src/fam_os/adapters/systemd/lifecycle.py` | User-systemd lifecycle implementation and resource-group locator |
| `src/fam_os/adapters/systemd/__init__.py`, `README.md` | Adapter exports and ownership |
| `src/fam_os/adapters/cgroup/paths.py` | Replaceable, traversal-safe cgroup-v2 root and group paths |
| `src/fam_os/adapters/cgroup/parsing.py` | Pure counter, ceiling, event, and pressure parsers |
| `src/fam_os/adapters/cgroup/observer.py` | Read-only service resource snapshot composition |
| `src/fam_os/adapters/cgroup/__init__.py`, `README.md` | Adapter exports and ownership |
| `tests/fixtures/systemd/` | Synthetic active-service property output |
| `tests/fixtures/cgroup/` | Synthetic cgroup-v2 memory-controller tree |
| `tests/unit/test_supervisor_contracts.py` | Supervisor invariant tests |
| `tests/unit/test_systemd_commands.py` | Exact bounded command-construction tests |
| `tests/unit/test_systemd_lifecycle.py` | Fake-driven start, status, stop, and failure tests |
| `tests/unit/test_cgroup_parsing.py` | Controller parser and unbounded-limit tests |
| `tests/unit/test_cgroup_observer.py` | Complete snapshot, degradation, and malformed-data tests |
| `tests/hardware/systemd_cgroup_smoke.py` | Opt-in real user-service lifecycle test |
| `docs/decisions/0006-user-systemd-and-cgroup-boundary.md` | Lifecycle and resource-boundary ADR |
| `README.md`, `MASTER_PLAN.md`, component READMEs | Current status, evidence, ownership, and next step |

## Public interfaces

- `ServiceState`
- `PressureScope`
- `ResourceLimits`
- `ServiceDefinition`
- `ServiceStatus`
- `ResourceEvent`
- `PressureSample`
- `ResourceCeiling`
- `ResourceSnapshot`
- `ResourceSnapshot.event_count(name)`
- `ServiceLifecycle`
- `ResourceObserver`
- `SupervisorError`
- `ServiceLifecycleError`
- `ResourceObservationError`
- `SystemdUserSettings`
- `SystemdUserServiceLifecycle`
- `CgroupV2Paths`
- `CgroupV2ResourceObserver`
- `ControlGroupLocator`

These are source-level Python interfaces. Authorization and external serialization are not implied and remain later plan work.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: 57 tests passed, 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
FAM_SYSTEMD_SMOKE=1 PYTHONPATH=src python3 -m unittest tests.hardware.systemd_cgroup_smoke -v
```

Result: 1 live user-systemd and cgroup smoke test passed in 0.057 seconds.

```bash
cd <REPO_ROOT>
python3 -m unittest discover -s tests -v
```

Result: all 10 parent RNF tests passed, 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
python3 -m compileall -q src tests
```

Result: completed successfully with no syntax errors.

The codebase knowledge graph was refreshed in fast mode with 1,058 nodes and 3,541 edges. It found the queried lifecycle port, user-systemd adapter, cgroup observer, snapshot contract, start-command builder, and pressure parser. Graph-augmented search found no parent `rnf` import under `FAM_OS/src/`. System commands and cgroup roots remain confined to adapters.

```bash
cd <REPO_ROOT>
npx -y larry-dev@latest setup
```

Result: 165 files indexed, 28 artifacts written, verification clean.

No implementation file exceeds 149 lines. All implementation functions remain below the 50-line target.

## Evidence and artifacts

The live adapter smoke used this deliberately small, non-sensitive service definition:

| Fact | Result |
|---|---:|
| Service | `fam-phase17-smoke.service` |
| Command | `/usr/bin/sleep 20` |
| Scope | User systemd |
| Memory ceiling | 67,108,864 bytes |
| Swap ceiling | 0 bytes |
| CPU quota | 25 percent |
| Task ceiling | 8 |
| Observed lifecycle state | Active |
| Observed cgroup snapshot | Present |

The test stopped the service in `finally`. A post-test systemd query returned `LoadState=not-found` and `ActiveState=inactive`, confirming that the collected transient unit was removed.

## Known limitations and risks

- The adapter only supports user-scoped transient services.
- A successful start does not imply application readiness.
- The shared Phase 1 command runner reports failure without structured exit-code or stderr details.
- Transient environment values are passed as command arguments and must not contain secrets.
- Missing optional cgroup files degrade to absent fields, so future policy must explicitly handle incomplete snapshots.
- Resource observation currently covers the cgroup-v2 memory controller and memory pressure only; CPU, I/O, PID, thermal, and energy observations remain later work.
- No retry, restart, timeout termination, crash recovery, or abandoned-unit reconciliation exists.
- The live smoke proves local mechanics, not the Phase 3 authorization or privilege security model.
- Direct cgroup mutation is intentionally absent to avoid conflicting with systemd ownership.

## Operational notes

The only live mutation was a temporary user-scoped `/usr/bin/sleep` service. It used a 64 MiB memory ceiling, no swap, a 25 percent CPU quota, and an eight-task ceiling. Cleanup removed it. No model, existing service, package, configuration, cgroup file, device permission, or system unit was modified.

## Recommended next entry point

Begin Phase 1.8. Map parent `rnf/verifier.py` with the graph, preserve its five existing extraction and sandbox tests, and split trusted candidate extraction/policy from sandbox command construction and execution. Keep verifier-owned guidance separate from model output and document that the Phase 1 sandbox is not yet a hardened hostile multi-tenant boundary.
