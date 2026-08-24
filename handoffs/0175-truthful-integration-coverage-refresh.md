# Handoff 0175: Truthful integration coverage refresh

**Date:** 2026-07-18  
**Plan step:** Phase 16 governance re-audit during Phase 23  
**Status:** Complete  
**Previous handoff:** `0174-query-bound-extractive-grounding.md`

## Objective

Restore the authoritative integration status after later implementation made
the Phase 16 maturity manifest and final-audit documents materially stale.

## Gap confirmed

The coverage manifest still said Scheduler did not enforce eviction, thermal,
or foreground-pressure policy after handoffs 0172–0173 implemented those paths.
It also described the Expert Factory as a component-only demonstration after
the signed installed Phase 22 exit completed QLoRA training, held-out
evaluation, packaging, canary, activation, rollback, retirement, and removal.
Two MCP evidence references named files that do not exist. The final audit still
claimed there were no unchecked Master Plan items and reported the obsolete
842-test/166-schema baseline.

## Scope completed

- Refreshed Scheduler, Expert Fabric, verification, UI, installed-service,
  governance, and Expert Factory evidence and gap statements.
- Advanced Expert Factory maturity to operationally proven using its signed
  installed aggregate exit while retaining the Phase 23 clean-profile gap.
- Corrected the two MCP handoff paths.
- Updated `NEXT_STEPS.md` to reflect completed Phase 22, production residency,
  current UI Factory routes, complete same-host peer recovery, and signed update
  capabilities.
- Replaced the stale final-audit conclusion with the exact open Phase 21.7 and
  Phase 23 requirements and the current 1,245-test/286-schema baseline.
- Added contract regressions requiring every coverage evidence path to resolve
  and preventing Scheduler/Expert Factory status from reverting to the stale
  pre-implementation claims.

## Files changed

- `configs/integration/coverage.json`
- `NEXT_STEPS.md`
- `docs/operations/FINAL_MASTER_PLAN_AUDIT.md`
- `tests/contract/test_integration_coverage.py`
- `handoffs/README.md`

## Validation

Run the integration coverage contract, static configuration/schema tests,
repository-wide Ruff, schema rendering check, and full source suite after this
documentation/contract correction is combined with the next audit change.

## Remaining work

- Phase 21.7 remains dependent on a second physical Linux machine.
- All Phase 23 checkboxes remain open until their direct installed evidence
  exists.
- This truth refresh does not itself create clean-profile, soak, human-review,
  or fresh-user release-candidate evidence.

## Recommended next entry point

Continue the Phase 23 audit with release-matrix infrastructure. Keep profiles,
suites, installed scenarios, CPU/full hardware runs, soak, Console authority,
human review, and lifecycle qualification as separately evidenced gates rather
than one god script.
