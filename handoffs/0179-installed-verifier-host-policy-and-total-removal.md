# Handoff 0179: Installed verifier host policy and total removal

**Date:** 2026-07-18  
**Plan step:** Phase 23.5 failure audit and Phase 23.8 readiness  
**Status:** Source corrections complete; installed gates remain open  
**Previous handoff:** `0178-phase23-installed-hardware-and-console-qualification.md`

## Objective

Investigate the failed 24-hour candidate without weakening isolation, audit the
remaining Phase 23.8 lifecycle, and implement every product gap found before
restarting final qualification.

## Root causes

1. The development terminal carried a named AppArmor profile that authorized
   unprivileged user namespaces; a normal systemd user service was truly
   `unconfined` and transitioned into Ubuntu's restrictive
   `unprivileged_userns` profile.
2. `NoNewPrivileges=true` correctly prevented both `aa-exec` and systemd from
   applying a more permissive profile inside that service.
3. Both normal declared verification and Factory canaries constructed their own
   unconfigured Bubblewrap runners.
4. `fam-os remove` removed only the signed prefix and unit link. It left state,
   models, identities, runtime credentials/sockets, managed Ollama state, and
   the VS Code connector.
5. No Phase 23.8 runner covered the required fresh-profile lifecycle.

## Implementation

- Signed and packaged `packaging/systemd/fam-os-userns`.
- Added host-policy detection and `fam-os host-security diagnose`.
- Kept the main daemon under `NoNewPrivileges=true`; only a short-lived
  manager-created verifier service receives `AppArmorProfile=fam-os-userns`.
- Kept Bubblewrap's capability drop, network denial, read-only runtime, tmpfs,
  task/RAM/no-swap limits, and output binding unchanged.
- Injected one configured sandbox into ordinary and Factory verification.
- Classified systemd AppArmor setup exit 231 as unavailable, not candidate
  failure.
- Added exact owner/UID/purpose/path markers to state and runtime roots.
- Added confirmed complete removal with preflight validation, both service
  stops, owned unit/connector cleanup, runtime/state/model deletion, and prefix
  deletion last.
- Hardened VS Code managed-target discovery against forged marker filenames.
- Added the small `tools/phase23_lifecycle/` installed lifecycle runner.

## Validation completed

- The packaged profile parses with AppArmor parser skip-load mode.
- A nested manager-created verifier service succeeds from a
  `NoNewPrivileges` parent using an already loaded development profile as a
  mechanics probe.
- The source `BubblewrapSandboxRunner` completes the same probe with output 42.
- Selecting the missing dedicated profile returns `unavailable`, isolation
  `none`, and an exact profile reason.
- Focused verifier, host-security, root-marker, removal, connector, CLI,
  release-assembly, and lifecycle tests pass.
- Ruff passes on all changed source, test, and tool targets checked so far.
- Strict mypy passes on the new sandbox, host-security, owned-root, removal, and
  lifecycle boundaries.

## External prerequisite and plan truth

This host requires a password for `sudo`; the implementation agent did not load
the system profile and did not substitute the unrelated `vscode` profile.
Follow `docs/operations/APPARMOR_VERIFIER_PROFILE.md` as the administrator, then
run the installed host-security diagnosis.

- Phase 23.5 remains open. Its 24-hour clock must restart from zero.
- Phase 23.8 remains open. The new runner must pass against the final post-soak
  candidate.
- Phase 21.7/physical 23.3 and independent-human 23.7 remain unchanged.

## Next entry point

Load `fam-os-userns`, run `fam-os host-security diagnose`, run a short lifecycle
preflight, then start the fresh 24-hour soak. After a passing soak, run the
Phase 23.8 lifecycle against that exact signed release candidate and trust key.

