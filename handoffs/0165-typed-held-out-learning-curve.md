# Handoff 0165: Typed held-out learning curve

**Date:** 2026-07-18  
**Plan step:** Phase 22.4-22.7  
**Status:** Partial  
**Previous handoff:** `0164-installed-console-monotonic-task-updates.md`

## Objective

Replace semantically ambiguous held-out evaluation with typed deterministic
verification and run real QLoRA learning-curve checkpoints until the fixed
promotion gate identifies a releasable specialist.

## Scope completed

- Added complete-or-absent held-out evaluation kind, verifier, and requirement
  metadata through capture, encrypted persistence, canonical sealing, schemas,
  Console capture, and evaluator loading.
- Added compatible exact-text, final-integer, safe-refusal, honest-refusal, and
  Python-test evaluation paths.
- Added explicit 256, 512, 1,000, 2,500, 5,000, and diverse-2,500 sample plans with fixed partitions
  and train-count-derived optimizer steps.
- Ran full encrypted preflights and real RTX 5080 QLoRA training/evaluation for
  the 1,000, 2,500, and 5,000 plans.
- Used a bounded Gemma 26B development-teacher probe to identify valid refusal
  vocabulary and diversify non-held-out safety and honesty training data.
- Preserved signed non-promotable decisions and owner-private evidence while
  removing held-out plaintext.

## Explicitly not completed

- A zero-failure promotable specialist.
- Conversion, package signing, disabled install, canary, activation, rollback,
  or retirement; the release boundary correctly rejects current adapters.
- Signed installed-product Phase 22 qualification.

## Architecture and decisions

ADR 0140 makes held-out semantics part of the sealed dataset contract and keeps
evaluation gates fixed across the comparable learning-curve series. Aggregate
decisions may select a later plan; evaluation content may not feed training.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/expert_factory/dataset_provenance.py` | Typed source metadata |
| `src/fam_os/expert_factory/dataset_sealing.py` | Metadata-bound canonical records |
| `src/fam_os/adapters/training/evaluation_worker.py` | Deterministic typed verifiers |
| `tools/phase22_specialist_exit/` | Fixed plans and physical checkpoint orchestration |
| `docs/decisions/0140-typed-held-out-verifiers-and-fixed-learning-curve.md` | Durable decision |

## Public interfaces

Held-out source schemas now expose nullable evaluation kind, verifier, and
requirement fields as one complete-or-absent group. The specialist exit accepts
`--sample-plan` values for explicit learning-curve plans.

## Validation

Ruff and strict Mypy pass the Phase 22 exit tooling. Thirty-one focused unit,
integration, sealing, evaluator, and scenario tests pass. The 2,500 preflight
retained all 2,868 records and passed all 2,868 source verifications.

## Evidence and artifacts

- `artifacts/training/phase22-stable-toposort-balanced1000-20260718-01/evidence.json`
- `artifacts/training/phase22-stable-toposort-balanced2500-20260718-01/evidence.json`
- `docs/decisions/0140-typed-held-out-verifiers-and-fixed-learning-curve.md`

## Known limitations and risks

- The 5,000 candidate still has one safety and three policy failures; unchanged
  semantic templates saturated despite the larger count.
- Repeated held-out use can bias selection; only aggregate signed metrics are
  used, and suite changes start a new comparison series.
- The current all-pairs near-duplicate pass scales poorly at 5,000 examples and
  must be indexed before a later 10,000 checkpoint.

## Operational notes

Normal `fam-os-current-test` service was restored after physical runs.
Checkpoint evidence files are mode `0600`; held-out plaintext paths are absent.

## Recommended next entry point

Preflight and run `diverse2500` against the unchanged held-out records and the
new verifier environment. Only if its signed decision is promotable may Phase
22.7 conversion begin; otherwise improve independently verified data diversity
rather than increasing count blindly.
