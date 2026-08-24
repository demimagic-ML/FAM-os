# Handoff 0219: Corrected installed integration lifecycle

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 signed installed lifecycle evidence  
**Status:** Partial  
**Previous handoff:** `0218-release-signed-integration-recipes.md`

## Objective

Prove Docker, process/API, release recipe trust, persistence, and owner controls
from the installed wheel without accidentally importing repository source.

## Scope completed

- Removed repository `PYTHONPATH` from the qualification scenarios.
- Copied test-only modules into the isolated environment while keeping `fam_os`
  exclusively installed under that environment's `site-packages`.
- Ran positive and deliberately failing release-recipe trust fixtures.
- Ran real bounded loopback HTTP and digest-pinned PostgreSQL lifecycles.
- Ran encrypted migration-0030 persistence, replay, compensation, and terminal-state tests.
- Ran authenticated Console confirmation and owner-UID Shell schema/transport controls.
- Ran homogeneous backend routing and mixed/absent fail-closed fixtures.
- Repeated all 18 scenarios under both declared profile labels.
- Verified zero FAM process scopes, Docker containers, and Docker networks remained.

## Explicitly not completed

- Independently enforced profile cgroups or a second physical host.
- One single scenario chaining a real owner grant through Console start, process
  launch, product restart, Shell inspection, and real reconciliation.
- Browser, mixed local cluster, retained artifacts, volumes, secrets, dynamic
  ports, or allowlisted egress.

## Architecture and decisions

This corrects the evidence method from Handoff 0215: that qualifier checked one
site-packages identity but then set repository `PYTHONPATH` for the actual
Docker test. Attempt 2 runs the scenarios with no repository import path. Test
code is copied separately and is not product implementation.

## Files changed

| Path | Purpose |
|---|---|
| `tools/run_phase27_integration_environment_qualification.py` | Correct installed multi-backend lifecycle qualifier |
| `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt2.json` | Passing corrected installed evidence |

## Public interfaces

No runtime interface changed. The qualification schema retains version 1 and
now covers the broader installed lifecycle scenario matrix.

## Validation

```bash
.verification-venv/bin/python \
  tools/run_phase27_integration_environment_qualification.py \
  --output artifacts/engineering/phase27/integration-environment-installed-20260719-attempt2.json \
  --repository . \
  --builder-python .verification-venv/bin/python
```

Result: PASS in 18.429703 seconds. Each declared profile label passed 18 tests.
The installed module was loaded from the temporary environment's
`site-packages/fam_os/__init__.py`. Wheel SHA-256:
`a1aac01ed65aab389cadf26e9d863edda0d363050f8a7f53a639afc13534bf14`.
Signer public-key SHA-256:
`813a4d0d41613dfc618b5c966d1aa9ca0c87b79ca429f96a23b808b7f4a55629`.

## Evidence and artifacts

- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt2.json`
- Measured host: x86-64, 24 logical CPUs, 65,447,104 KiB RAM, kernel
  6.17.0-35-generic.

## Known limitations and risks

- The two profile runs are labels on the same host and do not enforce distinct
  ceilings; the artifact states physical capacity, not profile compliance.
- The ephemeral signer proves integrity within this qualifier, not promotion to
  the production trust root.
- Wheel bytes changed between successive local builds, so this is exact-build
  evidence, not reproducible-wheel evidence.
- The scenarios cover the boundary components but not yet one real chained
  owner/restart transaction.

## Operational notes

No FAM process scope, labeled Docker container, or labeled Docker network was
left after either profile run.

## Recommended next entry point

Build one installed end-to-end scenario using a real persistent owner grant,
Console start of the signed process API, simulated product restart with the
same encrypted database/candidate state, owner-UID Shell inspection, and exact
restart reconciliation. Then implement the real-browser backend.
