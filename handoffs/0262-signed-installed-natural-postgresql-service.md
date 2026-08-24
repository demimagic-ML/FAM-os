# Handoff 0262: Signed installed natural PostgreSQL service

**Date:** 2026-07-19  
**Plan step:** Installed component evidence for Phase 27.12, 27.13, 27.16, and 30.1  
**Status:** Partial (`installed_component_tested`; product exit remains blocked)  
**Previous handoff:** `0261-natural-postgresql-service-composition.md`

## Objective

Prove that the ADR 0225 natural PostgreSQL service is contained in one fresh
signed complete release, imports no product code from the checkout, runs the
real Docker lifecycle, and preserves the independent host-security result.

## Scope completed

- Added the real natural PostgreSQL integration to the installed-package
  qualifier.
- Built complete seven-component release
  `phase30-natural-postgresql-20260719-2` with a fresh Ed25519 key.
- Installed it under a new isolated `/tmp` prefix without changing the live
  activated release or service.
- Rejected checkout import leakage and proved `fam_os` loaded from the
  immutable installed release.
- Loaded 415 installed schema roots plus both signed Python integration recipes.
- Passed 107 installed-package-first tests with zero failures/errors.
- The installed real PostgreSQL row rechecked exact image digest, separate
  secret grant planning, stable `integration:postgresql` consumer, file-only
  password injection, signed `pg_isready`, no host port, and exact cleanup.
- Confirmed no FAM integration container or network remained afterward.
- Ran independent installation and host-security diagnosis. Installation is
  healthy; production verification remains unavailable because the root-owned
  `fam-os-userns` profile is absent.

## Explicitly not completed

- The live service on `127.0.0.1:8765` was not updated or restarted.
- No owner secret was provisioned and no production/external database changed.
- No PostgreSQL endpoint, SQL migration, backup/restore, transaction test, or
  schema/data receipt was added.
- The host AppArmor profile was not loaded, and no claim of overall product
  passage is made.
- Independent profiles, MySQL, soak, and human security review remain open.

## Files changed

| Path | Purpose |
|---|---|
| `tools/run_phase30_natural_integration_installed.py` | Include the real natural PostgreSQL installed row |
| `artifacts/product/phase30/natural-postgresql-install-20260719-01/evidence.json` | Durable signed installed and host-gate evidence |
| `MASTER_PLANv2.md` | Installed maturity and remaining gap |
| `MASTER_PLAN.md` | Companion-plan evidence |
| `MASTER_PLANv2_STATUS_AUDIT.md` | Current installed component state |
| `MASTER_PLANv2_COMPLETION_PROMPT.md` | Resumable exact baseline |
| `handoffs/README.md` | Append handoff sequence |

## Validation

```bash
/usr/bin/python3.12 -I tools/run_phase30_natural_integration_installed.py \
  --installed-root /tmp/fam-os-phase30-natural-postgresql-install-20260719-2/active \
  --repository /home/demimagic/Desktop/NewLLM/FAM_OS \
  --expected-schemas 415

/tmp/fam-os-phase30-natural-postgresql-install-20260719-2/bin/fam-os \
  --prefix /tmp/fam-os-phase30-natural-postgresql-install-20260719-2 diagnose

/tmp/fam-os-phase30-natural-postgresql-install-20260719-2/bin/fam-os \
  --prefix /tmp/fam-os-phase30-natural-postgresql-install-20260719-2 \
  host-security diagnose
```

Results:

- Installed qualification: 107 tests, 0 failures, 0 errors, 15.407 seconds.
- Installed module:
  `/tmp/fam-os-phase30-natural-postgresql-install-20260719-2/releases/phase30-natural-postgresql-20260719-2/python/fam_os/__init__.py`.
- Installed recipes:
  `integration.python.root-api@1.0.0` and
  `integration.python.static-http@1.0.0`.
- Schema count: 415.
- Installation diagnosis: healthy, issues `[]`.
- Host-security diagnosis: exit 1, `status=unavailable`, `isolation=none`,
  absent `fam-os-userns`.

Identities:

- wheel SHA-256:
  `75f3fc71b54ee4d3e0aba9101b1fbb614e2a9b175ac9a0a13605296646975882`;
- manifest SHA-256:
  `8ed83883498d45ba636ff545985b0a1dd7f1aef81e31606bff1c58bbb5fb3e51`;
- signer key ID: `phase30-natural-postgresql-test-2`.

## Evidence and artifacts

- `artifacts/product/phase30/natural-postgresql-install-20260719-01/evidence.json`
- `/tmp/fam-os-phase30-natural-postgresql-build-20260719-2/bundle/manifest.json`
- `/tmp/fam-os-phase30-natural-postgresql-install-20260719-2/.fam-os-signed-installation.json`

## Known limitations and risks

- Test modules are loaded from the repository while all FAM_OS implementation
  imports resolve from the installed release. The runner checks this identity
  before executing the suite.
- The cached PostgreSQL image content digest is host/platform specific and is
  not independently qualified on the minimum profile.
- `installed_component_tested` is deliberately narrower than
  `operationally_proven`; the artifact's top-level `passed` remains false.

## Operational notes

The first build attempt used the installation-prefix path instead of the prior
build wheelhouse and therefore assembled a dependency-incomplete bundle. It was
never installed. Attempt 2 used all 32 offline wheels and is the only evidence
candidate. No live unit, active release, owner state, host profile, or external
resource changed.

## Recommended next entry point

Use the installed component as the frozen baseline for a broker-attested,
non-production PostgreSQL endpoint and typed migration executor. Do not widen
the isolated template or mark 27.12 complete from container health.
