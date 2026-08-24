# Handoff 0187: Workspace proposal repair and escalation

**Date:** 2026-07-18  
**Plan step:** Phase 19.15 corrective integration  
**Status:** Source and signed installed correction complete  
**Previous handoff:** `0186-authenticated-console-launch-correction.md`

## Objective

Replace the opaque workspace parameter failure seen in the installed Console
with bounded structural repair, stronger-model escalation, and an honest result
when a broad plan exceeds the existing-file patch capability.

## Scope completed

- Added strict nonempty plan, change-count, path, and UTF-8 content validation.
- Added a strict non-action `unavailable_reason` object for unsupported scope.
- Fed exact parser/binder feedback and observed paths into one repair attempt.
- Added one plan-budgeted escalation that excludes the failed model and asks the
  scheduler for the strongest fitting local expert.
- Added `application_mutation` to both strong experts' signed and packaged
  runtime scopes after live evidence proved they were otherwise ineligible.
- Capped both added generations to their durable 2,048-token reservations.
- Stabilized prepare-action progress text so a hidden model change cannot alter
  one Shell/Console revision and crash the monotonic client reducer.
- Added typed terminal failure-reason metadata and deterministic Console/Shell
  messages that state no action was executed.
- Added focused unit, lifecycle, and end-to-end workspace regressions.

## Explicitly not completed

- No raw terminal, unrestricted shell, new-file, deletion, package-install, or
  arbitrary-command authority was introduced.
- A broad generated plan is not automatically converted into executable steps.
- Existing workspace limits remain one to four observed UTF-8 files and the
  provider's total-byte bound.
- Phase 21.7 and remaining Phase 23 external gates are unchanged.

## Architecture and decisions

ADR 0164 keeps action authority in Core. Model output can be repaired or
escalated, but cannot grant itself paths or capabilities. Attempt reservations
reuse the production plan-global budget. Failure detail is typed policy
metadata and is excluded from safe terminal evidence.

## Validation

Focused workspace, retry, lifecycle, and gateway tests passed. Ruff passed all
changed source and tests, and Mypy passed the eight affected source modules.
The complete source suite passed 1,405 tests with two declared skips. Final log:
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-18T19-29-41-745Z.log`.

The immediately preceding full run hit the previously observed transient
`shell.core_unavailable` race in one approval test. The exact test passed in
isolation, then the unchanged complete suite passed. Both logs are retained in
the evidence artifact.

## Installed proof

Release `fam-os-workspace-repair-20260718-22` first proved the actionable safe
failure but exposed that the strong expert catalog lacked mutation intent.
Release 23 corrected the scope and a live owner workspace task durably recorded
one repair, one escalation, 4,096 reserved tokens, final selection
`laguna-xs.2:q4_K_M`, and `application.action.scope_unsupported`; no requested
new file existed afterward. That run exposed the same-revision Shell progress
bug.

Final release `fam-os-workspace-repair-20260718-24` keeps prepare-action progress
stable, completes the same unsupported operation in Shell without a client
exception, diagnoses healthy, serves Console HTTP 200, and its installed
scheduler selects Laguna as the strongest fitting mutation expert when the 7B
model is excluded.

## Evidence

- `artifacts/product/phase19/workspace-proposal-repair-20260718.json`
- `docs/decisions/0164-invalid-workspace-proposals-repair-before-failure.md`
- Full-suite log above

## Known limitations and risks

- If no different strong expert fits the live resource policy, Core terminates
  with the same actionable invalid-proposal result after the repair attempt.
- A valid but semantically poor complete-file proposal still requires owner
  preview and approval; post-write verification proves bytes, not design quality.
- Multi-file autonomous implementation needs additional typed tools and a
  stepwise planner rather than a larger JSON payload.

## Recommended next entry point

Add typed create-file and allowlisted command/test providers as separate
approval-aware capabilities before promising broad plan implementation.
