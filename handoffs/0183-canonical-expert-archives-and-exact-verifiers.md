# Handoff 0183: Canonical expert archives and exact verifiers

**Date:** 2026-07-18  
**Plan step:** Whole-Master-Plan corrective audit, Phases 2, 6, and 18  
**Status:** Complete in source and included in the next signed installed release  
**Previous handoff:** `0182-exact-package-scopes-and-strict-json.md`

## Objective

Finish the signed catalog authority audit by removing ambiguous archive members
and verifier supersets.

## Scope completed

- Split catalog archive, configuration, and scope validation into focused
  modules.
- Rejected duplicate, traversal, absolute, and non-canonical archive members.
- Required exact equality between runtime-scope and package verifier sets.
- Removed the stale undeclared Nomic verifier requirement.
- Kept provider manifests and runtime catalog decoding strict.

## Explicitly not completed

- This handoff does not complete the physical two-host, 24-hour soak, or human
  review gates.

## Architecture and decisions

ADR 0160 makes canonical archive membership and exact verifier reconstruction
part of signed expert package authority.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/production/model_catalog_archive.py` | Canonical signed archive loading |
| `src/fam_os/core/production/model_catalog_config.py` | Strict catalog/provider document loading |
| `src/fam_os/core/production/model_catalog_scopes.py` | Exact expert and verifier scope reconstruction |
| `src/fam_os/core/production/model_catalog.py` | Focused catalog composition |
| `tests/unit/test_packaged_runtime_catalog.py` | Archive and scope regressions |
| `docs/decisions/0160-signed-expert-archives-require-canonical-members-and-exact-verifiers.md` | Durable policy |

## Public interfaces

No new public command was added. Previously ambiguous signed expert archives
and verifier-superset scopes now fail closed.

## Validation

```bash
.verification-venv/bin/python -m unittest discover -s tests -t .
```

Result: 1,383 tests passed with two declared skips after the continuing audit.
The corrected package/catalog state is included in signed installed release
`fam-os-workspace-20260718-02`.

## Evidence and artifacts

- `docs/decisions/0160-signed-expert-archives-require-canonical-members-and-exact-verifiers.md`
- `artifacts/product/phase19/workspace-tools-20260718.json`

## Known limitations and risks

- Other release and Factory archive readers require their own duplicate-member
  audit; this decision does not silently claim those separate paths.

## Operational notes

No migration is required for canonical existing packages. Invalid archives must
be rebuilt and re-signed.

## Recommended next entry point

Read ADR 0161 and handoff 0184 for the owner-workspace tool boundary, then
continue the remaining whole-plan archive-reader audit.

