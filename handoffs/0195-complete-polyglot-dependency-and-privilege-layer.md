# Handoff 0195: Complete polyglot dependency and privilege layer

**Date:** 2026-07-18  
**Plan step:** Phase 27.2–27.9  
**Status:** Complete  
**Previous handoff:** `0194-signed-polyglot-execution-foundation.md`

## Objective

Complete production recipe coverage, isolated supply-chain evidence, signed
receipt verification, and external broker boundaries, then qualify the matrix
from a freshly installed signed artifact.

## Scope completed

- Added release-owned specifications for every required ecosystem/purpose gate
  and deterministic Ed25519 recipe construction.
- Added candidate-only dependency staging with exact direct package names,
  manifest/lock digests, SBOM, license, vulnerability, destination, download,
  installation-size, and artifact evidence.
- Added signed engineering receipt verification and fail-closed output flooding.
- Added bounded Unix broker clients for host administration/global installation.
- Passed all twelve positive and deliberately failing language fixtures from a
  fresh venv installation of an Ed25519-signed built wheel.

## Explicitly not completed

- Phase 31 full-host requalification, 24-hour soak, and independent review.

## Architecture and decisions

ADR 0170 remains controlling: Core admits signed recipes and delegates concrete
dependency, process, secret, and privileged effects to adapters or external
brokers. Global installs remain distinct from project dependencies.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/production_recipes.py` | Complete release recipe coordinates |
| `src/fam_os/adapters/dependencies/isolated.py` | Candidate dependency staging and evidence |
| `src/fam_os/adapters/host_admin/unix_broker.py` | External privileged broker transport |
| `src/fam_os/verification/engineering.py` | Signed receipt verdict |
| `tools/run_phase31_signed_engineering.py` | Signed built-wheel installed qualification |

## Public interfaces

`ToolRecipeSpecification`, `sign_recipe_specification`,
`IsolatedDependencyResolverAdapter`, `UnixHostAdministrationBroker`, and
`SignedEngineeringReceiptVerifier`.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_engineering_execution tests.integration.test_polyglot_engineering_sandbox -v
PYTHONPATH=src:. .verification-venv/bin/python tools/run_phase31_signed_engineering.py --output artifacts/engineering/phase31/signed-installed-engineering-20260718-attempt2.json
```

Result: the focused source suite and signed installed matrix pass. Installed
evidence runs all twelve ecosystems twice and the 66-test engineering suite;
the complete installed runner took 81.13 seconds.

## Evidence and artifacts

- `artifacts/engineering/phase31/signed-installed-engineering-20260718-attempt2.json`
- `docs/decisions/0170-engineering-execution-uses-signed-recipes-and-external-privilege.md`

## Known limitations and risks

- The two named engineering workload runs are bounded CPU-capable tests; they do
  not themselves prove full-host accelerator utilization.
- Concrete root broker deployment still depends on platform packaging and owner
  authentication configuration.

## Operational notes

The runner builds a new wheel, signs and verifies its bytes, installs it into a
fresh venv, and records the imported `site-packages` path. It leaves no service.

## Recommended next entry point

Read ADR 0171 and Handoff 0196, then inspect design asset sanitization.
