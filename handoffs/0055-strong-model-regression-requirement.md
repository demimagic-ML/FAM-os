# Handoff 0055: Strong-model regression requirement

**Date:** 2026-07-16  
**Plan step:** Phase 6.6-6.7 and Phase 9.1/9.3 planning constraint  
**Status:** Complete  
**Previous handoff:** `0054-expert-hardware-compatibility.md`

## Objective

Make the already downloaded Laguna and Gemma experts, the immutable failed
smoke baseline, and its repair-quality lessons mandatory future Expert Fabric
regressions rather than historical one-off diagnostics.

## Scope completed

- Confirmed existing independent raw runs for exact Ollama tags
  `laguna-xs.2:q4_K_M` and `gemma4:26b`.
- Confirmed the repository already preserves the original 7B/14B failed-quality
  baseline and its `neighbor_only` and `min(ready)` failures.
- Confirmed ADR 0027 and handoff 0026 already implemented bounded trusted-test
  disclosure, four difficult examples, numbered requirements, strict AST
  conformance, and separate full-workstation runs.
- Strengthened Phase 6.6 benchmark metadata to retain attempt/repair/disclosure,
  conformance, and resource evidence.
- Required Phase 6.7 to package both installed strong models as escalation code
  experts without making them defaults.
- Required Phase 9.1/9.3 to rerun the named regression independently through
  both packages and prove bounded escalation from smaller tiers.
- Added the operational regression checklist to the workstation smoke guide.

## Explicitly not completed

- No new model run was needed: exact successful raw evidence already exists.
- No model was downloaded, modified, removed, or activated.
- Phase 6.6 metadata, Phase 6.7 package definitions, and Phase 9 benchmark
  implementation remain their respective implementation steps.

## Architecture and decisions

This reinforces ADR 0027 rather than superseding it. Strong models remain
escalation tiers selected after smaller experts are predicted or proven
insufficient. Repair context is useful only when bounded and explicitly allowed
by verifier disclosure policy; hidden tests and task requirements cannot be
silently exposed or weakened.

## Files changed

| Path | Purpose |
|---|---|
| `MASTER_PLAN.md` | Makes exact models and regression evidence mandatory in Phases 6 and 9. |
| `docs/operations/FULL_WORKSTATION_SMOKE.md` | Adds the repeatable strong-model regression checklist. |
| `handoffs/README.md` | Registers this append-only planning handoff. |

## Public interfaces

No runtime interface changed. The implementation acceptance gates now name the
two exact model tags and required benchmark evidence.

## Validation

```bash
python3 -m json.tool configs/benchmarks/full-workstation-verified-smoke-laguna.json
python3 -m json.tool configs/benchmarks/full-workstation-verified-smoke-gemma4-26b.json
PYTHONPATH=src:. python3 -m unittest tests.unit.test_verified_code_execution tests.unit.test_execution_helpers
larry index . && larry health .
```

Result: both benchmark configurations parsed as valid JSON; all 13 focused
repair/orchestration tests passed. Larry indexed 821 files / 2,509 symbols with
11,426 nodes / 43,997 edges; freshness and verification were clean. The code
knowledge graph was refreshed to 11,426 nodes / 44,039 edges.

## Evidence and artifacts

- `handoffs/0026-strong-model-quality-rerun.md`
- `docs/decisions/0027-diagnostic-repair-context-and-strict-conformance.md`
- `artifacts/workstation/20260716T122504578152Z/workstation-smoke-20260716-122820-440726.json`
- `artifacts/workstation/20260716T122504578152Z/workstation-smoke-20260716-122945-696264.json`

## Known limitations and risks

- Disclosed-test success is diagnostic repair evidence, not unseen-task
  generalization.
- Phase 6 packages must still pass current trust, compatibility, lifecycle, and
  activation gates before the regression can count as package-system evidence.

## Operational notes

The existing raw reports show Laguna passing after one strict repair and Gemma
passing initially under separate full-workstation runs. The immutable earlier
failed baseline remains unchanged.

## Recommended next entry point

Continue Phase 6.5 package lifecycle implementation. When Phase 6.6 begins,
model benchmark metadata must represent attempt index, repair disclosure,
strict conformance, verification outcome, and full-host resource measurements.
