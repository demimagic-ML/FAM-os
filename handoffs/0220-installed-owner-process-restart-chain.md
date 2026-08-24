# Handoff 0220: Installed owner process restart chain

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 installed owner/restart chain  
**Status:** Partial  
**Previous handoff:** `0219-corrected-installed-integration-lifecycle.md`

## Objective

Prove one real installed transaction from owner grant ceremony through process
launch, encrypted restart recovery, Shell inspection, and exact cleanup.

## Scope completed

- Added a real fixed-entry candidate HTTP API fixture.
- Activated a task/workspace/toolchain/resource-exact persistent grant through
  authenticated Console ceremony.
- Started the API through Console's confirmed integration route and real Core admission.
- Persisted the admitted plan, candidate, permit, start receipt, and audit under migration 0030.
- Closed secure storage while leaving the real systemd scope active.
- Reconstructed storage, repository, Core service, adapter, and product API.
- Reconciled exact candidate-recorded scope identities without relaunch or grant reconfirmation.
- Inspected terminal cleaned evidence through the owner-UID mode-0600 Shell.
- Proved the exact scope inactive and reaped the original test wrapper.
- Added the chain to both no-repository-`PYTHONPATH` installed profile runs.

## Explicitly not completed

- Independently enforced profile ceilings or a second physical host.
- Browser, mixed local cluster, retained artifact, product secret, dynamic port,
  or allowlisted-egress support.

## Architecture and decisions

No new ADR was required. This validates ADRs 0183, 0185, 0186, and 0187 together:
owner authority admits launch, persistence retains cleanup identity, restart
never relaunches, cleanup reduces authority, and both owner surfaces remain
adapters over one product API.

## Files changed

| Path | Purpose |
|---|---|
| `tests/integration/test_installed_process_owner_restart_chain.py` | Real chained lifecycle fixture |
| `tests/integration/installed_database_authority_support.py` | Console client accepts environment API |
| `tools/run_phase27_integration_environment_qualification.py` | Include chain in installed matrix |
| `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt3.json` | Passing installed chain evidence |

## Public interfaces

No runtime interface changed.

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.integration.test_installed_process_owner_restart_chain

.verification-venv/bin/python \
  tools/run_phase27_integration_environment_qualification.py \
  --output artifacts/engineering/phase27/integration-environment-installed-20260719-attempt3.json \
  --repository . \
  --builder-python .verification-venv/bin/python
```

Result: source chain passed in 4.783 seconds. Installed attempt 3 passed in
28.379978 seconds; each declared profile label passed 19 tests. Wheel SHA-256:
`ec8bf7324bff4c0ac994d8c3cbbdc4cd77eedf753425879ba0c0dadbce2e7fbc`.
Signer public-key SHA-256:
`7bdb5bd6afd28784ce09f7e7017c566d22b7cd1665b012b7ae53d67bd9002184`.

## Evidence and artifacts

- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt3.json`
- Measured host: x86-64, 24 logical CPUs, 65,447,104 KiB RAM, kernel
  6.17.0-35-generic.

## Known limitations and risks

- Both profile labels still run on one host without distinct cgroup ceilings.
- The qualifier signer is ephemeral and not the production release trust root.
- Browser and mixed-provider local-cluster lifecycle remain unimplemented.

## Operational notes

No FAM process scope remained after qualification.

## Recommended next entry point

Add a real-browser backend using a release-signed fixed Chromium recipe,
ephemeral owner-private profile, loopback-only DevTools or WebDriver transport,
bounded screenshots/logs, health, exact cleanup, and restart reconciliation.
