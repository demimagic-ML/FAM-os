# Handoff 0161: Held-out evaluation and signed denial

**Date:** 2026-07-17  
**Plan step:** Phase 22.5–22.6  
**Status:** Partial  
**Previous handoff:** `0160-real-qlora-backend-and-physical-smoke.md`

## Objective

Add the independent, one-use, held-out evaluation boundary and prove on the RTX
5080 that the real smoke adapter is denied rather than promoted without evidence.

## Scope completed

- Added immutable quality/safety/policy/unrelated and hardware comparison
  contracts with confidence bounds and hard promotion gates.
- Added self-verifying Ed25519 signatures to terminal comparison decisions.
- Added migration 0025 and encrypted owner-scoped approval, run, access,
  measurement, report, and decision persistence.
- Added an approval service that derives exact adapter, dataset, held-out,
  proposal, and capability lineage from a completed training receipt.
- Added a separate ephemeral evaluator workspace; held-out plaintext is never
  materialized in the training tree and is removed before its receipt commits.
- Added a network-denied Bubblewrap/systemd evaluator that loads the frozen base
  and PEFT adapter under identical deterministic generation settings and retains
  only hashes, pass/fail outcomes, latency, RAM, VRAM, and energy.
- Added authenticated Console collections and controls plus service CLI runtime
  composition for the evaluator.
- Changed Console training submission to a background lifecycle so the HTTP
  request does not remain blocked while the GPU worker runs.
- Ran the evaluator against the real `20260717-05` adapter and obtained the
  expected signed non-promotable decision.

## Physical result

- Evidence: `artifacts/training/phase22-physical-smoke-20260717-05/evaluation-evidence.json`
- Cases: 4 total; 1 held-out quality, 1 safety, 1 policy, 1 unrelated.
- Quality: incumbent 1/1, candidate 1/1; no improvement and only one sample.
- p95 latency: incumbent 2,297,789 us; candidate 3,028,036 us.
- Peak RAM: incumbent 5,132,132,352; candidate 5,889,531,904 bytes.
- Peak VRAM: incumbent 1,415,023,616; candidate 1,449,364,480 bytes.
- Energy: incumbent 445 J; candidate 653 J.
- Network denied: true.
- Held-out plaintext: 341 bytes materialized, discarded, zero paths retained.
- Decision: signed by `device-eb07ff0e774b77e821de1200`, promotable false.
- Reasons: sample count, minimum/confident improvement, safety, policy, and
  scheduler packaging gates.

## Key files

- `src/fam_os/expert_factory/evaluation.py`
- `src/fam_os/product/storage/factory_evaluation_repository.py`
- `src/fam_os/product/storage/migrations/0025_factory_evaluations.sql`
- `src/fam_os/product/factory_evaluations.py`
- `src/fam_os/product/factory_evaluation_workspace.py`
- `src/fam_os/adapters/training/evaluation_worker.py`
- `src/fam_os/adapters/training/nvidia_evaluation_backend.py`
- `src/fam_os/product/composition/factory_evaluation.py`
- `tools/phase22_evaluation_exit/`
- `configs/training/qwen3-1.7b-evaluation-suite.jsonl`

## Validation

Focused evaluation, repository, workspace, production database, schema
round-trip, Console, product service, and training lifecycle tests pass. Ruff
passes the changed source, and the evaluation exit tooling passes strict Mypy.
The schema catalog now renders 273 artifacts.

## Explicitly not completed

- A 256+ approved learning-curve dataset and promotable held-out improvement.
- Pinned GGUF conversion, signed Expert Fabric packaging, disabled install,
  scheduler canary, or activation (22.7).
- Crash-resume access-attempt accounting for an evaluator interrupted after
  held-out disposal but before terminal report commit.
- Physical service-stop evidence for a running training worker.
- Signed installed-product repetition of the Phase 22 controls.

## Next entry point

Phase 22.7 must reject the current adapter because its decision is
non-promotable. Build the pinned conversion/package/canary source path and prove
that denial first. Then construct an approved, leakage-controlled learning curve
starting at 256 examples; only an adapter with a signed promotable decision may
cross conversion and installation authority.
