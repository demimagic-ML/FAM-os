# Handoff 0189: Strict engineering results and receipts

**Date:** 2026-07-18  
**Plan step:** Phase 24.4  
**Status:** Complete for step 24.4; Phase 24 remains in progress  
**Previous handoff:** `0188-typed-engineering-authority-contracts.md`

## Objective

Make proposed, executed-and-verified, externally published, and unavailable
engineering outcomes structurally distinct before any new effect provider is
connected.

## Scope completed

- Added fixed `EngineeringResultKind` values for change-set proposals, verified
  change-set receipts, publication proposals, publication receipts, and
  unavailable capabilities.
- Added one strict contract for each result kind and registered five new schema
  roots.
- Required before/after workspace snapshots, changed operation/path identities,
  verifier runs, and evidence before a verified change-set receipt can exist.
- Required an independent publication proposal, publish authority, owner
  checkpoint identity, observed remote revision, evidence, and postcondition
  verification for a publication receipt.
- Extended cross-contract checks through task, proposal, snapshot, tool-run,
  publication proposal, and checkpoint identities.
- Added tests proving a model-supplied discriminator cannot relabel one outcome
  as another.

## Explicitly not completed

- No change-set or publication result is emitted by the production lifecycle.
- No Git remote, package registry, shell, or other external effect was invoked.
- Executed-unverified and verification-waived assurance remain Phase 24.9 work.
- Delegation modes, grant lifecycle, break-glass approval, product projections,
  and the Phase 24 exit gate remain open.

## Architecture and decisions

This change implements the result side of ADR 0165. A verified receipt is a
constructible Core contract only when independent evidence identities are
present; its eventual producer must additionally validate those evidence
records. Publication is a separate proposal/checkpoint/receipt sequence and is
not implied by workspace modification approval.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/results.py` | Strict engineering result and receipt contracts. |
| `src/fam_os/core/engineering/__init__.py` | Exports the public result family. |
| `src/fam_os/schemas/catalog.py` | Registers five result schemas. |
| `src/fam_os/schemas/references.py` | Validates result and publication references. |
| `schemas/v1alpha1/fam.core.*.schema.json` | Adds five generated result schemas. |
| `tests/contract/schema_engineering_fixtures.py` | Adds representative result documents. |
| `tests/contract/test_schema_roundtrip.py` | Round-trips the new roots. |
| `tests/contract/test_schema_compatibility.py` | Checks strict exact-alpha compatibility. |
| `tests/contract/test_cross_contract_references.py` | Checks result reference failures. |
| `tests/unit/test_engineering_contracts.py` | Checks result discriminators and receipt evidence. |
| `MASTER_PLANv2.md` | Records Phase 24.4 evidence. |

## Public interfaces

- `EngineeringResultKind`
- `EngineeringProposalResult`
- `VerifiedChangeSetReceipt`
- `EngineeringPublicationProposal`
- `EngineeringPublicationReceipt`
- `EngineeringCapabilityUnavailable`
- Five new `fam.core.* /v1alpha1` schema roots using
  `fam.core.engineering/v1alpha1`.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_engineering_contracts \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references
```

Result: 41 tests passed.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
git diff --check -- src/fam_os/core/engineering src/fam_os/schemas/catalog.py \
  src/fam_os/schemas/references.py tests/contract \
  tests/unit/test_engineering_contracts.py MASTER_PLAN.md MASTER_PLANv2.md \
  docs/decisions handoffs
```

Result: all 302 generated schemas validated; diff whitespace check passed.

The complete suite was not rerun because Handoff 0188 records the current host
Python dependency failure from the immediately preceding run. This change did
not alter that dependency or the unrelated failing verifier path.

## Evidence and artifacts

- `docs/decisions/0165-engineering-authority-is-typed-and-core-admitted.md`
- `schemas/v1alpha1/fam.core.verified-change-set.schema.json`
- `schemas/v1alpha1/fam.core.publication-receipt.schema.json`

## Known limitations and risks

- Evidence IDs are cross-document references, not proof by themselves. The
  production receipt policy must resolve them to trusted verifier records.
- Publication target policy and remote postconditions are not yet implemented.
- The five contracts share the Phase 24 alpha version and will require explicit
  migration if later semantics change their wire shape.

## Operational notes

No service, package, external repository, credential, or operating-system state
was changed.

## Recommended next entry point

Continue with Phase 24.5. Read `src/fam_os/core/engineering/results.py`, the
action-intent firewall, expert-scope manifests, Console/Shell result projection,
and `configs/integration/coverage.json`. Add one authority at a time without
making any effect runtime-reachable before its grant and verification policy.
