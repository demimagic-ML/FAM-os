# ADR 0030: Harden the Supervisor boundary from an explicit threat model

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 3 mechanisms had focused positive and negative tests but no single attacker
model. Adversarial review found that shell-free execution alone was insufficient:
commands beginning with `--` could cross the systemd-run or Bubblewrap option
boundary. A live namespace test also showed that a workload acting as PID 1 could
outlive FAM's command timeout under systemd's long default stop grace.

The audit file rejected symlinks at the file path but did not reject an insecure
or symlinked direct parent directory. Transport identities and command/environment
payloads also needed explicit control-character and size bounds.

## Decision

Adopt `docs/security/SUPERVISOR_THREAT_MODEL.md` as the Phase 3 security model and
make each primary threat executable where possible.

Insert explicit option terminators before all service commands in systemd and
Bubblewrap vectors. Bound service IDs, context/grant identities, argument count
and length, environment count and value length, and reject ASCII control
characters.

Make systemd termination explicit with `KillMode=control-group`,
`SendSIGKILL=yes`, and a bounded `TimeoutStopSec`. Require safe absolute
Bubblewrap configuration paths. Require the audit file's direct parent to be a
current-user, nonsymlink directory that is not group/world writable.

Add a security suite that proves the namespace, ownership, user-systemd,
option-boundary, path, resource-exhaustion, non-goal, and layer-import controls.
Add a combined live Phase 3 exit-gate smoke.

## Consequences

- Option-looking workload arguments cannot mutate adapter options.
- Namespace PID 1 behavior cannot extend stop beyond the configured grace before
  systemd kills the complete control group.
- Malformed transport data is rejected before adapter use.
- Audit placement in `/tmp` or a symlinked/writable direct parent fails closed.
- Supervisor source cannot import intelligence layers without breaking tests.
- Command semantic authorization still belongs to trusted Core/package policy;
  Phase 3 does not become an executable-content classifier.
- The configured stop grace becomes an observable workload constraint.

## Alternatives considered

1. Rely on shell-free subprocess execution: rejected because option parsers still
   interpret leading `--` arguments.
2. Let the systemd default stop timeout apply: rejected because it exceeded the
   Supervisor adapter timeout and produced false failure while work continued.
3. Treat all same-user directories as safe audit parents: rejected because a
   writable/symlinked direct parent permits path replacement.
4. Put command-semantic analysis in Supervisor: rejected as intelligence/policy
   creep; approved manifest binding belongs outside this boundary.
5. Document threats without executable tests: rejected because the controls are
   cheap to regress accidentally.

## Evidence

- `docs/security/SUPERVISOR_THREAT_MODEL.md`
- `tests/security/test_supervisor_threats.py`
- `tests/hardware/supervisor_phase3_exit_smoke.py`
- `src/fam_os/supervisor/contracts.py`
- `src/fam_os/supervisor/access.py`
- `src/fam_os/supervisor/access_contracts.py`
- `src/fam_os/adapters/systemd/commands.py`
- `src/fam_os/adapters/systemd/settings.py`
- `src/fam_os/adapters/bubblewrap/service_access.py`
- `src/fam_os/adapters/audit/jsonl.py`
