# Handoff 0135: Signed complete release installation

**Date:** 2026-07-17  
**Plan step:** Phase 17.7  
**Status:** Complete  
**Previous handoff:** `0134-profile-derived-worker-cgroups.md`

## Scope completed

- Portable relative-path Ed25519 release manifest.
- Deterministic archives for offline wheelhouse, 181 schemas, experts, compiled
  VS Code connector, Console, units, and five migrations.
- Offline target installation and staged import/asset health checks.
- Atomic activation, update, rollback, diagnosis, repair, unit enable/disable,
  and total removal commands.
- Installed service composition now opens encrypted migrated storage, enters
  explicit recovery mode on key loss, manages Ollama, and shuts it down.
- Fresh built release returned `MANAGED_READY` through its installed Shell and
  six live Console sections after restart.

## Validation

The full source suite passes 875 tests with seven declared skips. The built
release passed install, launcher import, managed inference, restart, Console,
update, rollback, diagnosis, and removal. Evidence is in
`artifacts/product/phase17/signed-installed-release.json`.

## Known limitations and risks

- The production gateway remains the narrow fixed-model gateway until Phase 18;
  therefore the Phase 17 exit is not overstated as complete yet.
- Unit enable/disable code is implemented but the temporary acceptance install
  was launched directly to avoid replacing the user's currently enabled service.
- The test signing key was ephemeral and is not a release trust anchor.

## Recommended next entry point

Begin Phase 18.1. Compose admission, durable repositories, plan lifecycle,
routing, attempts, final policy, and task persistence behind one production
gateway. Remove `LocalInferenceShellGateway` from `LocalProductService` only when
natural chat and recovery tests pass through the replacement.
