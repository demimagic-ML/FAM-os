# Handoff 0263: Natural PostgreSQL migration lifecycle

**Date:** 2026-07-19  
**Plan step:** Phase 27.12, 27.13, and 30.1 partial  
**Status:** Partial (`installed_component_tested`; product exit remains blocked)  
**Previous handoff:** `0262-signed-installed-natural-postgresql-service.md`

## Objective

Turn fixed isolated PostgreSQL health into a typed, reversible, evidence-bound
natural migration lifecycle without granting cluster administration or
claiming external database support.

## Scope completed

- Added strict plan/receipt contracts and two schema roots.
- Planned at most four exact forward/reverse SQL pairs from current candidate
  files and rejected PostgreSQL meta/administrative SQL.
- Created and physically validated fixed restricted role `fam_migrator` and
  fixed candidate database `fam_candidate`.
- Streamed bounded SQL and decrypted backup bytes to fixed Docker argv without
  a shell, host plaintext file, host port, or writable container root.
- Proved baseline, encrypted backup, forward state, transaction rollback,
  reverse baseline, repeat-forward equality, and fresh restore equality.
- Bound exact authority decisions, service/runtime/permit, candidate, and
  changeset evidence into preview and fresh-owner post-apply repetition.
- Composed the verifier through the natural product service and installed
  qualifier.
- Built and installed signed release
  `phase30-postgresql-migrations-20260719-3`; 119 package-first tests passed.

## Explicitly not completed

- No external, remote, or production PostgreSQL target was attached.
- No host port, connection string, or production mutation was authorized.
- MySQL remains absent.
- The live `127.0.0.1:8765` service was not replaced.
- Required host AppArmor policy, both final profiles, soak, and independent
  human review remain open.

## Architecture and decisions

ADR 0226 records the fixed non-superuser role, bounded stdin transport,
encrypted retained backup, exact lifecycle, and fail-closed recovery boundary.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/postgresql_verification.py` | Typed plan/receipt contracts |
| `src/fam_os/core/engineering/postgresql_verification_service.py` | Core authority service |
| `src/fam_os/adapters/database/postgresql_*.py` | Planning, admission, fixed commands, storage, verification |
| `src/fam_os/adapters/integration/docker_client.py` | Bounded fixed-command stdin transport |
| `src/fam_os/product/natural_engineering_integration.py` | Candidate and post-apply orchestration |
| `src/fam_os/product/composition/postgresql_verification.py` | Product composition |
| `tools/run_phase30_natural_integration_installed.py` | Installed package-first proof |
| `artifacts/product/phase30/natural-postgresql-migration-install-20260719-01/evidence.json` | Durable evidence |

## Public interfaces

- `fam.core.postgresql-integration-verification-plan/v1alpha1`
- `fam.core.postgresql-integration-verification-receipt/v1alpha1`
- `PostgreSQLIntegrationVerificationPlan`
- `PostgreSQLIntegrationVerificationReceipt`

## Validation

```bash
PYTHONPATH=src python3 -m unittest -v \
  tests.integration.test_natural_postgresql_environment

/usr/bin/python3.12 -I tools/run_phase30_natural_integration_installed.py \
  --installed-root /tmp/fam-os-phase30-postgresql-migrations-install-20260719-3/active \
  --repository /home/demimagic/Desktop/NewLLM/FAM_OS \
  --expected-schemas 417
```

Results: 2 physical tests passed; 129 affected and 41 architecture tests
passed; 417 schemas validated; 119 installed-package-first tests passed in
20.113 seconds. Full discovery ran 1,868 tests with the known 15 absent-host-
profile failures and one unrelated missing checkout MCP SDK error. No FAM
container or network remained.

## Evidence and artifacts

- `artifacts/product/phase30/natural-postgresql-migration-install-20260719-01/evidence.json`
- `/tmp/fam-os-phase30-postgresql-migrations-build-20260719-3`
- `/tmp/fam-os-phase30-postgresql-migrations-install-20260719-3`
- ADR 0226

## Known limitations and risks

- Successful PostgreSQL plan/receipt evidence is attached durably with the
  changeset; a crash in the preceding narrow window cleans and fails closed
  instead of reconstructing success.
- Installed component passage is narrower than live product/profile passage.

## Operational notes

The live service and host policy were untouched. The signed isolated install is
healthy. Host-security diagnosis remains unavailable until the owner loads
`fam-os-userns`.

## Recommended next entry point

Persist the PostgreSQL verification checkpoint before candidate environment
cleanup, then add only a broker-attested non-production external target. Do not
infer production database authority from the isolated lifecycle.
