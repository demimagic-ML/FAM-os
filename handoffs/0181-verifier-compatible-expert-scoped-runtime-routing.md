# Handoff 0181: Verifier-compatible expert-scoped runtime routing

**Date:** 2026-07-18  
**Plan step:** Whole-Master-Plan corrective audit, Phases 8 and 18  
**Status:** Source implementation and whole-suite qualification complete  
**Previous handoff:** `0180-phase23-lifecycle-diagnosis-and-tool-import-correction.md`

## Objective

Audit the Phase 8 verifier package boundary and Phase 18 installed routing path
for enforcement rather than documentation, then correct every affected runtime
consumer without weakening shared-model resource accounting.

## Defects confirmed

- Selection ignored `RuntimeModelEntry.verifier_ids`.
- Repair, escalation, fallback, and remote recovery did not carry the durable
  declaration's verifier requirement into model selection.
- Signed runtime composition retained multiple package bindings only after an
  initial correction, but still exposed aggregate model authority when one
  shared expert was disabled.
- Peer capabilities and residency identity collapsed shared provenances to one
  arbitrary expert.
- Durable rows could reintroduce disabled signed scopes at startup.
- Factory activation could mutate lifecycle state before discovering verifier
  incompatibility or an existing model-reference owner.

## Implementation

- Added exact verifier-compatible candidate filtering to every local selection
  path.
- Added signed `expert_scopes` for all seven runtime artifacts and all ten
  selected expert identities, including the three Llama scopes and two Qwen-VL
  scopes.
- Bound every scope to signed manifest capability domains and declared verifier
  IDs, and required the aggregate model entry to equal the exact scope union.
- Rebuilt enabled model routes from enabled scopes while retaining one physical
  model entry and one residency lease.
- Persisted scoped entries and restored only exact current-release or Expert
  Factory lineage.
- Emitted peer declarations per expert scope and used a deterministic runtime
  residency identity for shared weights.
- Rejected unavailable verifier bindings and model-reference collisions before
  factory lifecycle, storage, or catalog mutation.

## Files changed

| Area | Paths |
|---|---|
| Catalog and routing | `src/fam_os/core/production/model_catalog.py`, `model_selection.py`, `inference_starter.py`, `verification_flow.py`, `remote_recovery.py` |
| Product composition | `src/fam_os/product/service.py`, `peer_capabilities.py`, `model_residency.py` |
| Factory and persistence | `src/fam_os/product/factory_activation.py`, `factory_lifecycle.py`, `storage/expert_enablement_repository.py` |
| Signed package configuration | `configs/packages/runtime/model-catalog.json`, packaged copy, affected expert manifests |
| Regression coverage | packaged catalog, model policy, peer capability, residency, factory, repository, verifier, remote execution, and reference-package tests |

## Validation

Focused Ruff and Mypy checks passed. The focused behavioral matrix passed 47
tests before the ownership guard and 31 affected tests after it.

```bash
.verification-venv/bin/python -m unittest discover -s tests -t .
```

Result: 1,365 tests passed with two declared skips and no failures.

The canonical and packaged runtime catalog files compare byte-for-byte, every
changed JSON document parses, and the runtime verifier union is a subset of the
activated production verifier catalog.

## Remaining work

- Build the next signed candidate and repeat the installed profile matrix after
  the rest of the Master Plan audit is complete.
- The independent Phase 21.7, Phase 23.5, Phase 23.7, and Phase 23.8 gates remain
  governed by their existing physical, soak, human-review, and AppArmor
  prerequisites.
- Continue the requirement-by-requirement audit; this handoff proves only the
  corrected verifier and expert-scope boundary.

## Decision

ADR 0158 records the durable split between physical model identity and signed
expert authority. Do not collapse shared provenances back into a model-keyed
dictionary.

