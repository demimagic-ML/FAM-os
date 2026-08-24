# Handoff 0246: Signed installed documentation generation

**Date:** 2026-07-19  
**Plan step:** Phase 30.1, 30.5, 30.6, and 30.9  
**Status:** Partial (`installed_tested`; live production verifier blocked)  
**Previous handoff:** `0245-generated-documentation-apply-gate.md`

## Objective

Turn the documentation admission gate into an installed natural-loop producer
without giving a model, client, generator, or raw shell trusted mutation
authority.

## Scope completed

- Added an Ed25519-signed documentation recipe contract and trusted catalog.
- Added release-owned recipes for diagram, API-reference, runbook, changelog,
  and generated-code-manifest output.
- Packages and loads those recipes only from the verified installed expert
  archive under the release signer.
- Added deterministic bounded byte generators; they receive source bytes but
  no filesystem, network, process, credential, or approval authority.
- Added deterministic natural-intent policy selection; model output does not
  choose the recipe.
- Persists the exact request before any generated candidate effect.
- Routes ownership, regeneration, and generated outputs through the existing
  authorized, budgeted, restart-safe candidate editing service.
- Re-hashes and admits the real candidate output, then includes it in signed
  verification, preview, transactional apply, reverification, Git commit, and
  rollback.
- Fails relevant tasks truthfully when the active release lacks the signed
  documentation catalog.
- Corrected local Git delivery to compare Git-representable file effects rather
  than explicit directory-creation operations; directory moves remain
  fail-closed without file-expanded evidence.
- Built and installed signed release `phase30-governance-20260719-3` and loaded
  all five recipes from that installed release with no checkout import.

## Explicitly not completed

- Automatic regeneration after a stale source/output report.
- Digest binding and stale detection for the shared ownership/regeneration
  instruction files themselves.
- Automatic generation of complete requirement-to-code-test-evidence traces.
- Live production-verifier execution while `fam-os-userns` is unavailable.
- Final both-profile/dependency matrices, 24-hour soak, and independent human
  security review.
- Remaining incident/review governance and Phase 27/29 gaps.

## Architecture and decisions

ADR 0211 makes a documentation recipe a release-signed byte-producer identity,
not a shell command. Core owns selection, intent persistence, candidate edits,
receipt admission, and all later lifecycle gates.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/documentation.py` | Signed recipe contract. |
| `src/fam_os/core/engineering/documentation_recipes.py` | Signature catalog and generation bounds. |
| `src/fam_os/core/engineering/documentation_policy.py` | Natural-intent requirement selection and governed output paths. |
| `src/fam_os/core/engineering/production_documentation_recipes.py` | Five release-owned recipe specifications. |
| `src/fam_os/adapters/crypto/documentation_recipes.py` | Ed25519 signing adapter. |
| `src/fam_os/adapters/documentation/deterministic.py` | Bounded deterministic generators. |
| `src/fam_os/product/composition/documentation_recipes.py` | Verified installed catalog loader. |
| `src/fam_os/product/natural_engineering_documentation.py` | Intent-before-effect generation coordinator. |
| `src/fam_os/product/natural_engineering_execution.py` | Attach generated content before signed verification. |
| `src/fam_os/product/engineering_documentation_api.py` | Persist and validate signed generation intent. |
| `src/fam_os/product/release_assembly.py` | Ship signed recipes in the expert archive. |
| `src/fam_os/core/engineering/local_git_delivery.py` | Translate explicit directories to Git file effects. |
| `tests/unit/test_documentation_recipes.py` | Signature, bounds, generators, policy, and unavailable-catalog tests. |
| `tests/integration/test_natural_engineering_checkpoint.py` | Natural API documentation through checkpoint, commit, and rollback. |
| `artifacts/product/phase30/governed-documentation-install-20260719-01/evidence.json` | Installed identities, tests, failed attempt, and host blocker. |

## Public interfaces

- `SignedDocumentationRecipe`
- `SignedDocumentationRecipeCatalog`
- `DocumentationGenerationService`
- `DocumentationRequirementPolicy`
- `ProductEngineeringLoopApi.begin_documentation_generation(...)`
- `installed_documentation_recipe_catalog(...)`

## Validation

```bash
env PYTHONPATH=src:. python3 tools/render_contract_schemas.py
```

Result: 407 schemas rendered and validated.

```bash
larry run env PYTHONPATH=src:. python3 -m unittest <affected suites>
larry run env PYTHONPATH=src:. python3 -m unittest discover \
  -s tests/architecture -p 'test_*.py'
```

Result: 80 affected tests and 41 architecture tests passed. Raw logs:

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T09-29-17-361Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T09-29-30-511Z.log`

The first signed attempt, `phase30-governance-20260719-2`, correctly failed its
health gate because its fresh offline wheelhouse omitted declared dependencies.
The gate was not weakened. After completing the wheelhouse, release
`phase30-governance-20260719-3` installed healthily.

```bash
/usr/bin/python3.12 -I \
  /tmp/fam-os-phase30-governance-20260719-3/installed_test_runner.py
```

Result: 74 installed-package tests passed in 4.403 seconds; the module imported
from the immutable installed release, all five documentation recipes loaded,
and all 407 schemas were present. Raw log:
`/home/demimagic/.larry/-tmp/runs/run-2026-07-19T09-33-43-350Z.log`.

```bash
/tmp/fam-os-phase30-governance-install-20260719-3/bin/fam-os \
  --prefix /tmp/fam-os-phase30-governance-install-20260719-3 \
  host-security diagnose
```

Result: exit 1, fail-closed `unavailable`; required AppArmor profile
`fam-os-userns` is not loaded.

## Evidence and artifacts

- `artifacts/product/phase30/governed-documentation-install-20260719-01/evidence.json`
- `/tmp/fam-os-phase30-governance-20260719-3/bundle/manifest.json`
- `/tmp/fam-os-phase30-governance-install-20260719-3/.fam-os-signed-installation.json`
- ADR 0211

## Known limitations and risks

- Installed natural lifecycle tests use deterministic fixture verification;
  they are not a substitute for the blocked production Bubblewrap verifier.
- The common ownership and regeneration files are required and created through
  the candidate service but are not yet themselves digest-bound in staleness
  reports.
- The deterministic keyword policy is safe and inspectable but not yet a
  versioned persisted selection receipt.
- Wheel construction is not yet byte-reproducible across repeated builds; this
  remains covered by the open release-artifact work.

## Operational notes

No live service, active owner release, systemd unit, port, repository remote,
or user project was changed. The signed candidate is isolated under `/tmp`.

## Recommended next entry point

Bind governance-file digests and add bounded automatic regeneration after a
stale report, then generate real requirement trace records from the same task
evidence. Continue with the remaining incident/review lifecycle before the
next integrated signed candidate.
