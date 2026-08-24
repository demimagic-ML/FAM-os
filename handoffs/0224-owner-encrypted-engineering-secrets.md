# Handoff 0224: Owner encrypted engineering secrets

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 production secret-reference lifecycle  
**Status:** Partial  
**Previous handoff:** `0223-restart-safe-process-secret-files.md`

## Objective

Turn installed file-injection mechanics into an authenticated, encrypted,
owner-visible production capability and prove the complete path.

## Scope completed

- Added migration 0031 and owner-bound AES-GCM secret storage.
- Bound each reference to one exact tool key, consumer, state, and generation.
- Added provision, rotation, tombstone deletion, metadata list/inspect, and audit.
- Added exact single-use, two-minute, session-bound owner operation contexts.
- Fixed context consumption so invalid session/digest attempts cannot burn it.
- Composed the repository into Docker and process environment providers.
- Added authenticated metadata-only Console controls.
- Added three strict Shell schema roots, mode-0600 transport, client, dispatch,
  stable errors, and metadata-only responses.
- Strengthened the installed owner/restart chain to provision through Console,
  activate exact `SECRET_USE`, run a real API consuming the file, restart,
  reconcile, erase the file root, and inspect terminal state through Shell.

## Explicitly not completed

- Forced cleanup of already-running environments when a reference rotates or deletes.
- External secret stores, direct disclosure, or automated credential rotation.
- Mixed-backend clusters, allowlisted egress, and portable browser packaging.
- Independently enforced physical profiles, soak, and human review.

## Architecture and decisions

ADR 0191 assigns durable encrypted reference ownership to product storage,
keeps plaintext resolution in the concrete provider, and makes both owner
surfaces metadata-only. It supersedes only ADR 0190's default-deny product
limitation; ADR 0190 remains authoritative for process-file lifetime.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/storage/migrations/0031_engineering_secrets.sql` | Durable schema |
| `src/fam_os/product/storage/engineering_secret_repository.py` | Encrypted lifecycle/provider |
| `src/fam_os/product/engineering_secret_api.py` | Authenticated owner facade |
| `src/fam_os/product/owner_engineering_authentication.py` | Secret purposes and atomic consumption |
| `src/fam_os/product/composition/core_storage.py` | Repository composition |
| `src/fam_os/product/composition/storage_unit.py` | Secure storage exposure |
| `src/fam_os/product/service.py` | Product/Console/Shell wiring |
| `src/fam_os/console/engineering_secret_routes.py` | Console controls |
| `src/fam_os/shell/engineering_secret_contracts.py` | Versioned Shell contracts |
| `src/fam_os/adapters/shell/engineering_secret_dispatch.py` | Product dispatch |
| `src/fam_os/shell/wire.py` | Wire kinds and decoding |
| `src/fam_os/adapters/shell/client.py` | Owner client operations |
| `src/fam_os/adapters/shell/dispatcher.py` | Server dispatch/errors |
| `schemas/v1alpha1/fam.shell.engineering-secret-*.schema.json` | Strict schemas |
| `tests/integration/test_installed_process_owner_restart_chain.py` | Real installed chain |
| `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt8.json` | Installed evidence |

## Public interfaces

- `ProductEngineeringSecretApi`: provision, rotate, delete, inspect, list, audit.
- Shell roots `fam.shell.engineering-secret-query`, `-mutation`, and `-response`
  at `fam.shell.engineering-secret/v1alpha1`.
- Console routes under `/api/v1/engineering/secrets`.

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_engineering_secret_repository \
  tests.unit.test_engineering_secret_api \
  tests.integration.test_console_engineering_secrets \
  tests.unit.test_fam_shell_engineering_secret_transport -v

PYTHONPATH=src python3 -m unittest \
  tests.integration.test_installed_process_owner_restart_chain -v

.verification-venv/bin/python \
  tools/run_phase27_integration_environment_qualification.py \
  --output artifacts/engineering/phase27/integration-environment-installed-20260719-attempt8.json \
  --repository . --builder-python .verification-venv/bin/python

PYTHONPATH=src python3 -m unittest discover -s tests/architecture -t . -v
```

Result: the real owner chain passed in 1.615 seconds. The broader storage,
schema, transport, and environment suite passed 60 tests in 5.357 seconds;
all 41 architecture tests passed in 0.768 seconds. Installed attempt 8 passed
42 tests per same-host profile in 21.469728 seconds without checkout imports.
Wheel SHA-256:
`66723b5c927c604ea426957e3d621fa8045bcca405b1d4e411f667d46d1a34f3`.
Signer-key SHA-256:
`532589cab8eda3c58fac54ee6ee884f738a363412073f4af5765a7738a3519ce`.

## Evidence and artifacts

- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt8.json`
- `docs/decisions/0191-owner-engineering-secrets-are-encrypted-consumer-bound-and-metadata-only.md`

## Known limitations and risks

- Rotation/deletion does not interrupt an active materialization.
- Same-UID host processes remain in the owner trust boundary.
- Same-host profile labels are not independent physical evidence.
- Qualification uses an ephemeral signer.

## Operational notes

Qualification left no `fam-int-*` scope or process secret root.

## Recommended next entry point

Add an active environment-to-secret index and coordinate reference rotation or
deletion with exact environment cleanup before committing the lifecycle event.
Then resume mixed-backend orchestration and allowlisted egress.
