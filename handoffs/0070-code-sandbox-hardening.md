# Handoff 0070: Code sandbox hardening

**Date:** 2026-07-16  
**Plan step:** Phase 8.2  
**Status:** Complete  
**Previous handoff:** `0069-verifier-trust-activation.md`

## Completed

- Replaced unbounded `subprocess.run(capture_output=True)` buffering with
  streaming fixed-cap stdout/stderr drains.
- Kill timed-out process groups rather than only waiting for a direct child.
- Added a declared process rlimit alongside memory, CPU, file, FD, and core limits.
- Clear the Bubblewrap environment and restore only deterministic PATH/hash seed.
- Detect Bubblewrap namespace startup errors as fail-closed unavailability.
- Added output-flood, timeout, namespace-failure, command, and live smoke tests.
- Documented the exact security boundary and its non-VM/non-seccomp limitations.
- Captured canonical hostile-probe evidence on the current workstation.

## Evidence

`artifacts/verification/phase8.2/sandbox-security-probe.json` records that the
installed Bubblewrap cannot create the required namespace in this session. All
four containment probes return `unavailable`/`none`; none silently execute with
process-only isolation. The independent output flood retains exactly 333 bytes
and is killed at its 0.1 second wall budget. The busy loop is likewise killed.

## Operational consequence

This host/session cannot release results that require hostile-code Bubblewrap
containment until user namespaces become available or a stronger provider is
installed. This is a deliberate, visible denial rather than a workaround.

## Next entry point

Implement Phase 8.3 verifier composition: syntax must run without executing the
candidate; unit tests, type checks, and static analysis must each emit distinct
evidence, and release must require every acceptance component declared by policy.
