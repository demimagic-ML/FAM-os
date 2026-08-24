# ADR 0140: Held-out semantics are typed and learning-curve gates stay fixed

Status: Accepted

## Context

A held-out source previously carried only input and reference text. A generic
text-contains fallback could therefore classify safety, honesty, and unrelated
cases as quality, producing numerically valid but semantically false evidence.
Repeated adapter checkpoints also create pressure to tune against evaluation
content or weaken a gate to obtain a promotable result.

## Decision

Every held-out source used by the specialist evaluator carries a complete
evaluation triple: kind, verifier kind, and requirement identity. The triple is
captured under the dataset grant, encrypted at rest, bound into canonical sealed
partition bytes, and disclosed only to the evaluator. Partial metadata is
invalid. Evaluators reject incompatible kind/verifier pairs.

The initial verifier set is deterministic Python tests, exact text, bounded
final integer, safe refusal, and evidence-honest refusal. Verification behavior
is versioned in the sealed suite digest. A changed verifier or suite begins a
new comparable series; older runs remain diagnostic evidence.

Sample counts are explicit plans. Aggregate signed decisions may choose the next
plan, but dataset authors do not inspect held-out prompts, outputs, or failures.
Safety and policy continue to require zero failures, and quality confidence,
unrelated regression, hardware, and scheduler gates are not relaxed.

## Consequences

- Evaluation metrics describe the intended requirement instead of a generic
  string heuristic.
- Dataset manifests change when evaluation semantics change.
- Runs under different suite digests are not represented as one continuous
  learning curve.
- A non-promotable adapter remains auditable but cannot reach conversion.
- More training data may be expensive without guaranteeing promotion.

## Evidence

- `src/fam_os/expert_factory/dataset_provenance.py`
- `src/fam_os/expert_factory/dataset_sealing.py`
- `src/fam_os/adapters/training/evaluation_worker.py`
- `tools/phase22_specialist_exit/sample_plans.py`
- `artifacts/training/phase22-stable-toposort-balanced1000-20260718-01/evidence.json`
- `artifacts/training/phase22-stable-toposort-balanced2500-20260718-01/evidence.json`
