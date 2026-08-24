# Handoff 0249: Bounded candidate repair and final-state changesets

**Date:** 2026-07-19  
**Plan step:** Phase 30.1, 30.5, 30.7, and 30.9  
**Status:** Partial (`source_composed`)  
**Previous handoff:** `0248-postapply-failure-rollback-and-incident-closure.md`

## Objective

Connect a real failed signed candidate verification to one bounded repair,
reverification, exact final-state changeset, monitored incident recovery, and
ordinary local delivery without widening authority or exposing diagnostic
secrets.

## Scope completed

- Added one deterministic repair generation under the remaining shared task
  budget and bound it to the current candidate state.
- Counts failed and interrupted verifier attempts as monotonic command usage;
  replay of the same verification identifier is effect- and budget-idempotent.
- Labels sanitized verifier feedback as untrusted model data and excludes raw
  tool output, credentials, control sequences, and private host paths from
  durable diagnostic evidence and inference context.
- Persists typed remediation proposal and edit evidence, reruns installed
  signed recipes, records two ordered recovery observations, emits a structured
  report, and closes the incident after passing repaired verification.
- Derives the owner checkpoint from the actual final candidate against the
  original owner baseline, producing one authorized operation per final path.
- Rejects unauthorized build output, no-op final candidates, file/directory
  kind replacement, duplicate paths, and final state over task bounds.
- Selects only the final repaired verification set for changeset qualification;
  the failed attempt remains failure and incident evidence.
- Discloses executable-mode changes in the exact preview even when a final
  content patch also carries the candidate's final mode.
- Added a real temporary Git-repository integration that fails verification,
  repairs `app.py` from the intermediate value to the requested value, squashes
  two edits into one baseline-bound patch, reaches owner approval, applies,
  reverifies, commits once, closes the incident, and accounts four commands.

## Explicitly not completed

- Repair after generated documentation exists; that path currently stops so
  stale documentation cannot be approved.
- A separately scheduled later recovery probe independent from the repaired
  verification set.
- More than one repair or model escalation tier.
- Signed-installed, live Console/Shell, or production Bubblewrap proof of this
  branch.
- Remaining documentation/review governance, Phase 27/29 powers, final profile
  qualification, 24-hour soak, and independent human review.

## Architecture and decisions

ADR 0214 makes repair a bounded continuation of the existing candidate rather
than a parallel lifecycle. Core owns feedback redaction, state binding, final
state derivation, verification selection, and incident transitions. Adapters
continue to own filesystem observation/effects and tool execution. The model
proposes content only; it does not choose authority, recipes, hashes, passing
evidence, repair count, or approval.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/candidate_generation_service.py` | Bind repair intent, current candidate, feedback, and budget. |
| `src/fam_os/core/engineering/candidate_squash.py` | Derive bounded final owner-baseline operations and artifacts. |
| `src/fam_os/core/engineering/diagnostic_redaction.py` | Shared fail-closed diagnostic evidence/model redaction. |
| `src/fam_os/core/engineering/candidate_verification_service.py` | Sanitize verifier reasons before evidence persistence. |
| `src/fam_os/core/engineering/candidate_changeset_service.py` | Admit exact final operations and selected verification IDs. |
| `src/fam_os/core/engineering/master_loop.py` | Account failed verification evidence idempotently. |
| `src/fam_os/product/natural_engineering_repair.py` | Coordinate one real bounded repair. |
| `src/fam_os/product/natural_engineering_execution.py` | Select repair/failure branches and final evidence. |
| `src/fam_os/product/natural_engineering_incidents.py` | Record remediation, monitored recovery, report, and closure. |
| `src/fam_os/product/candidate_engineering_api.py` | Observe current candidate and build final-state checkpoint. |
| `src/fam_os/product/engineering_loop_api.py` | Expose current candidate, verification accounting, and selection. |
| `src/fam_os/adapters/filesystem/candidate_workspace.py` | Observe final entries and disclose combined mode changes. |
| `src/fam_os/adapters/bubblewrap/diagnostics.py` | Reuse Core diagnostic sanitizer. |
| `src/fam_os/adapters/bubblewrap/engineering.py` | Sanitize persisted tool diagnostics. |
| `src/fam_os/adapters/linux/raw_shell.py` | Sanitize persisted explicit-shell diagnostics. |
| `tests/integration/test_natural_engineering_incident.py` | Real repair, incident, squash, apply, reverify, and Git proof. |
| `tests/unit/test_candidate_squash.py` | Final-state, authority, type, ordering, and media tests. |
| `tests/unit/test_engineering_diagnostic_redaction.py` | Secret, path, control, truncation, and determinism tests. |

## Public interfaces

- `CandidateGenerationService.generate(..., repair_feedback=(), binding_candidate=None)`
- `squash_candidate_edits(...)`
- `sanitize_diagnostic_evidence(...)`
- `sanitize_diagnostic_feedback(...)`
- `ProductEngineeringLoopApi.current_candidate(...)`
- `ProductEngineeringLoopApi.record_failed_candidate_verifications(...)`
- `ProductEngineeringLoopApi.preview_candidate(..., verification_ids=...)`
- Natural approval response may include `repair_count`, a closed `incident`,
  and its `incident_evidence` after successful repair.

## Validation

```bash
larry run env PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_candidate_generation_service \
  tests.unit.test_candidate_changeset_service \
  tests.unit.test_candidate_squash \
  tests.unit.test_candidate_workspace \
  tests.unit.test_candidate_verification_service \
  tests.unit.test_engineering_diagnostic_redaction \
  tests.unit.test_runtime_diagnostics \
  tests.unit.test_engineering_execution \
  tests.unit.test_natural_engineering_execution \
  tests.unit.test_engineering_incident_service \
  tests.unit.test_local_git_delivery_service \
  tests.unit.test_product_engineering_loop_api \
  tests.unit.test_product_natural_engineering_api \
  tests.unit.test_fam_shell_natural_engineering \
  tests.unit.test_fam_shell_engineering_loop_transport \
  tests.integration.test_natural_engineering_incident \
  tests.integration.test_natural_engineering_checkpoint \
  tests.integration.test_natural_engineering_publication \
  tests.integration.test_console_natural_engineering \
  tests.integration.test_console_engineering_loop \
  tests.integration.test_product_service \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references \
  tests.security.test_engineering_adversarial
```

Result: 135 tests passed. Raw log:
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T10-14-25-475Z.log`.

```bash
larry run env PYTHONPATH=src:. python3 -m unittest discover \
  -s tests/architecture -t .
```

Result: 41 architecture tests passed. Raw log:
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T10-14-54-760Z.log`.

```bash
larry run env PYTHONPATH=src:. python3 tools/render_contract_schemas.py
node --check src/fam_os/console/static/natural_engineering.js
git diff --check
```

Result: all 408 schema artifacts rendered and validated; JavaScript syntax and
diff whitespace checks passed. Schema log:
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T10-14-54-772Z.log`.

## Evidence and artifacts

- ADR 0214
- The source validation logs above
- Temporary real-repository assertions in
  `tests/integration/test_natural_engineering_incident.py`

## Known limitations and risks

- Recovery receipts currently provide two ordered observations over the same
  repaired signed-verification set; an independently delayed observation is
  still required for stronger monitored-recovery evidence.
- Repair feedback retains bounded sanitized summaries, not raw diagnostic
  artifacts. This intentionally trades some debugging detail for credential
  safety.
- Existing signed candidate `phase30-governance-20260719-3` predates this
  source branch and does not prove it.

## Operational notes

No live service, active release, owner repository outside tests, remote, or
host policy was changed. Test repositories were temporary and removed.

## Recommended next entry point

Finish Phase 30.6 regeneration and governance binding so documentation-bearing
tasks can repair safely. Then finish Phase 30.8 review selection/remediation,
build the next signed candidate containing both incident repair and rollback
branches, and run installed qualification after the host sandbox prerequisite
is satisfied.
