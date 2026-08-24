# Handoff 0218: Release-signed integration recipes

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 installed process recipe trust  
**Status:** Partial  
**Previous handoff:** `0217-bounded-process-api-integration-environments.md`

## Objective

Enable the process/API backend in an installed product without any unsigned or
source-development recipe fallback.

## Scope completed

- Generated the initial Python loopback API recipe during release assembly.
- Signed the recipe and complete release with the same Ed25519 release key.
- Embedded recipes in the independently digest-bound expert archive.
- Added strict bounded archive loading and normal signed-catalog admission.
- Required recipe signer identity to equal the verified release signer.
- Composed process routing only when the installed catalog verifies.
- Added a single safe declared-port placeholder and fixed candidate API path.
- Proved a differently signed recipe is rejected and process-only composition
  works when Docker is absent.

## Explicitly not completed

- Signed installed owner lifecycle qualification for the process/API backend.
- Additional language/service recipes, browser recipes, or mixed clusters.
- Dynamic arbitrary candidate entry points or general argument placeholders.

## Architecture and decisions

ADR 0187 makes release verification a prerequisite to recipe admission. The
recipe signature does not grant engineering authority; it only defines a safe
mechanism that Core may invoke after owner grant admission.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/release_assembly.py` | Generate and package signed API recipe |
| `src/fam_os/product/composition/integration_recipes.py` | Verify and load installed recipes |
| `src/fam_os/product/composition/catalog_unit.py` | Expose active release root |
| `src/fam_os/product/service.py` | Pass verified catalog to environment composition |
| `src/fam_os/adapters/integration/process_environment.py` | Safe declared-port expansion |
| `tests/unit/test_installed_integration_recipes.py` | Positive and wrong-signer fixtures |

## Public interfaces

- `installed_integration_recipe_catalog(release_root)`
- `active_release_root()`
- Installed expert member `integration-recipes/python-http.json`
- Safe `{port:<declared-name>}` recipe placeholder

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.integration.test_process_api_integration_environment \
  tests.unit.test_installed_integration_recipes \
  tests.unit.test_release_bundle
```

Result: 6 tests passed in 5.569 seconds, including real HTTP health and cleanup.

## Evidence and artifacts

- `docs/decisions/0187-integration-recipes-are-dual-bound-to-the-installed-release.md`

## Known limitations and risks

- The initial fixed entry path requires candidate preparation before start.
- The catalog intentionally has no local-development process fallback.
- Installed end-to-end evidence has not yet exercised Console/Shell controls.

## Operational notes

Older signed releases without `integration-recipes/` continue safely with the
process backend unavailable. Tampered recipes fail product composition.

## Recommended next entry point

Extend `tools/run_phase27_integration_environment_qualification.py` to build the
new release, load the catalog from installed artifacts, start through owner
Console or Shell, restart/reconcile from encrypted migration-0030 state, and
prove zero scope leakage under both declared profiles.
