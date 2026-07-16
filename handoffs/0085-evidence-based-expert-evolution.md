# Handoff 0085: Phase 9.8 expert evolution rules

## Completed

- Added deterministic split, merge, and retirement thresholds.
- Added minimum sample enforcement and task-cluster matching.
- Added strict proposal/report contracts that forbid state mutation.
- Produced all three proposal types from fixture-bound benchmark evidence.
- Added three public schemas; the catalog now contains 103 artifacts.

## Evidence

- `artifacts/expert_fabric/phase9.8/expert-evolution-report.json`
- `tests/integration/test_expert_evolution_evidence.py`
- `tests/unit/test_expert_evolution_policy.py`
- `docs/protocols/EVIDENCE_BASED_EXPERT_EVOLUTION.md`
- `docs/decisions/0084-expert-evolution-is-proposal-only.md`

## Next

Validate the complete Phase 9 exit gate, refresh the code map, and then begin Phase 10.1 at the existing memory record/provenance schema boundary.
