# Handoff 0029: Supervisor threat model and adversarial exit gate

**Date:** 2026-07-16  
**Plan step:** Phase 3.7 threat model and security tests  
**Status:** Complete; Phase 3 exit gate passed  
**Previous handoff:** `0028-safe-service-recovery.md`

## Objective

Define the Supervisor's attacker model and trust boundaries, convert primary
threats into executable negative tests, harden discovered option/path/termination
gaps, and prove the complete Phase 3 dummy-service exit gate on the real host.

## Scope completed

- Added the canonical Supervisor threat model with assets, trust zones, attacker
  profiles, controls, fail-closed behavior, residual risks, and explicit claims.
- Added an adversarial security suite for identity/control injection, argument and
  environment exhaustion, systemd/Bubblewrap option injection, user/system scope,
  FAM ownership, grant/path injection, cgroup traversal, non-goals, and forbidden
  intelligence-layer imports.
- Bounded service IDs, command argument count/length, environment count/value
  length, and context/grant/evidence identities.
- Rejected ASCII control characters across transport identities, service commands,
  environment values, adapter command settings, and Bubblewrap paths.
- Added explicit `--` option terminators before workload commands in systemd-run
  and Bubblewrap vectors.
- Required safe absolute unique Bubblewrap runtime paths.
- Required a current-user, nonsymlink, non-group/world-writable audit parent in
  addition to existing no-follow/regular-file/0600 checks.
- Added explicit systemd control-group termination, SIGKILL fallback, and bounded
  stop grace for workloads that ignore SIGTERM as namespace PID 1.
- Added a combined live Phase 3 exit test for audited start, exact resource limits,
  cgroup observation, safe termination, final inactive/no-PID state, and complete
  ledger verification.
- Re-ran the real allowlist-only Bubblewrap access proof and failed-state recovery.
- Added ADR 0030 and this handoff; marked Phase 3 complete.

## Explicitly not completed

- The external authenticated local Supervisor transport is not implemented.
- Approved service command semantics/digests are not independently enforced by
  Supervisor; trusted Core/package policy still selects definitions.
- Registries are not crash-durable or multi-user.
- The local audit chain still lacks an external trusted head.
- FD-based host resource binding and race-free path pinning are not implemented.
- The dedicated packaged AppArmor policy and production install hardening remain
  later work.
- Host root and a fully compromised user account are outside the Phase 3 claim.

## Architecture and decisions

ADR 0030 records that shell-free execution is necessary but insufficient. Both
systemd-run and Bubblewrap have option parsers, so a workload beginning with `--`
requires an explicit argument boundary.

The first post-hardening Bubblewrap live rerun exposed a termination problem: a
namespace workload acting as PID 1 outlived FAM's 10-second adapter wait under
systemd's long default stop grace. The unit eventually stopped, but FAM correctly
reported failure. The final unit policy explicitly uses control-group kill,
SIGKILL fallback, and `TimeoutStopSec=3s`. The next live rerun stopped immediately
and passed isolation/cleanup.

The threat model treats authorizer configuration, allowlist mappings, adapter
executable paths, and Core-selected definitions as trusted inputs. It treats
workloads, serialized transport data, provider evidence, and model text as
untrusted. Supervisor source cannot import intelligence layers.

## Files changed

| Path | Purpose |
|---|---|
| `docs/security/SUPERVISOR_THREAT_MODEL.md` | Assets, attackers, controls, residuals |
| `docs/decisions/0030-supervisor-adversarial-boundary-hardening.md` | Security decision |
| `tests/security/test_supervisor_threats.py` | Executable attacker cases |
| `tests/hardware/supervisor_phase3_exit_smoke.py` | Combined live exit gate |
| `src/fam_os/supervisor/contracts.py` | Service/command/environment bounds |
| `src/fam_os/supervisor/access.py` | Strict caller identities |
| `src/fam_os/supervisor/access_contracts.py` | Strict grant/evidence identities |
| `src/fam_os/adapters/systemd/commands.py` | Option boundary and bounded stop policy |
| `src/fam_os/adapters/systemd/settings.py` | Safe command and stop-grace validation |
| `src/fam_os/adapters/bubblewrap/service_access.py` | Safe paths and option boundary |
| `src/fam_os/adapters/audit/jsonl.py` | Secure direct-parent requirement |
| `tests/unit/test_jsonl_audit_sink.py` | Writable/symlink parent attacks |
| `tests/unit/test_systemd_commands.py` | Option/kill/timeout command evidence |

## Public interfaces

- `SystemdUserSettings.stop_grace_seconds`
- stricter existing `ServiceDefinition`, `SupervisorCallContext`,
  `ServiceAccessGrant`, and `AccessApplicationEvidence` validation
- stricter existing `BubblewrapServiceAccessSettings` validation

No intelligence, system-service, root, or arbitrary-process capability was added.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.security.test_supervisor_threats \
  tests.unit.test_jsonl_audit_sink \
  tests.unit.test_supervisor_contracts \
  tests.unit.test_systemd_commands \
  tests.unit.test_bubblewrap_service_access -v
```

Result: all 34 focused adversarial/boundary tests passed in 0.044 seconds before
the final bounded-stop assertions; the subsequent focused 16-test stop/security
rerun also passed.

```bash
FAM_SUPERVISOR_PHASE3_SMOKE=1 PYTHONPATH=src:. \
  python3 -m unittest tests.hardware.supervisor_phase3_exit_smoke -v
FAM_BUBBLEWRAP_ACCESS_SMOKE=1 PYTHONPATH=src:. \
  python3 -m unittest tests.hardware.bubblewrap_service_access_smoke -v
FAM_SERVICE_RECOVERY_SMOKE=1 PYTHONPATH=src:. \
  python3 -m unittest tests.hardware.service_recovery_smoke -v
```

Final results: combined exit gate passed in 0.116 seconds, Bubblewrap allowlist
and cleanup passed in 0.033 seconds, and failed-state recovery passed in 0.147
seconds. The combined ledger contained six valid linked records and mode `0600`.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
python3 -m compileall -q src tools tests
```

Result: all 333 tests passed in 0.254 seconds, all 35 generated schemas matched,
and compilation completed successfully. Phase 3.6 closed with 323 tests.

An AST audit found no `src/` or `tools/` module at or above 300 lines and no
function at or above 50 lines.

Larry refreshed 473 files and verified clean. The codebase graph refreshed in
fast mode with 7,043 nodes and 21,603 edges.

## Known limitations and risks

- An authorized compromised Core can still select a dangerous user-level command;
  package digest/definition binding is future work.
- Trusted host mapping sources are path-based rather than pinned file descriptors.
- Same-user and root attackers exceed several local file/process isolation claims.
- Authentication transport, durable registries, external audit head, AppArmor
  packaging, and multi-user isolation remain open.
- Stop grace is bounded, but a wedged kernel task may still be unkillable; final
  state verification prevents a false successful report.
- Disk exhaustion and long-duration denial-of-service testing belong to Phase 14.

## Recommended next entry point

Begin Phase 4.1 with the existing `TaskRequest`, capability, approval, and
permission contracts. Implement deterministic admission that binds authenticated
principal/session/authority, validates expiry and requested capability scope,
creates an immutable admitted request or structured rejection, and has no model,
application, Ollama, systemd, or desktop dependency. Use in-memory authority and
replay registries with adversarial tests before routing begins.
