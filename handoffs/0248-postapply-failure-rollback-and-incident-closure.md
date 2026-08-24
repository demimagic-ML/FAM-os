# Handoff 0248: Post-apply failure rollback and incident closure

**Date:** 2026-07-19  
**Plan step:** Phase 30.1, 30.5, 30.7, and 30.9  
**Status:** Partial (`source_composed`)  
**Previous handoff:** `0247-typed-incident-preservation-and-diagnosis.md`

## Objective

Give a post-apply verification failure an exact owner-approved recovery action
and connect its real outcome to the incident rollback, report, and closure
chain without creating or rewriting Git history.

## Scope completed

- Added a pre-commit rollback checkpoint for an applied changeset that has no
  exact local Git delivery.
- Binds the checkpoint to the apply journal, paths, current Git head, and exact
  approval digest.
- Revalidates exact head and empty staging state before the filesystem effect;
  candidate journal checks still stop on path drift.
- Persists rollback intent, restores only unchanged FAM-owned paths, and records
  lifecycle rollback without claiming a Git action.
- Classifies delivery by exact changeset identity rather than task-global Git
  evidence, preserving multiple-checkpoint correctness.
- Reuses the stored rollback decision and receipts for effect-free retries.
- Advances the associated incident through typed rollback, post-incident
  report, and closure receipts; retries resume from intermediate incident
  stages and do not duplicate evidence.
- Reconstructs the failed applied checkpoint from durable task and incident
  state through natural progress.
- Added truthful Shell and Console recovery presentation that distinguishes
  failed uncommitted rollback from optional inverse-commit rollback.

## Explicitly not completed

- Model/tool repair of a failed candidate and a new remediation changeset.
- Monitored recovery after successful remediation verification.
- Automatic safe resumption of a task interrupted after apply but before a
  verifier result exists.
- Signed-installed, live Console/Shell, or production Bubblewrap proof of this
  branch.
- Remaining documentation/review governance, Phase 27/29 work, profile
  qualification, soak, and human review.

## Architecture and decisions

ADR 0213 separates uncommitted failure recovery from rollback of a verified
commit. Local Git contributes exact ref and staging preconditions but performs
no Git effect; candidate transactions own file restoration; Core owns lifecycle
and incident advancement; presentation adapters expose the exact checkpoint.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/local_git_delivery.py` | Exact pre-commit Git boundary and checkpoint. |
| `src/fam_os/product/candidate_engineering_api.py` | Admit rollback from the applied lifecycle stage. |
| `src/fam_os/product/engineering_loop_api.py` | Select exact committed/uncommitted rollback and record the right receipt shape. |
| `src/fam_os/product/natural_engineering_incidents.py` | Bind rollback outcome to report and closure, including resume. |
| `src/fam_os/product/natural_engineering_api.py` | Offer and reconstruct failed-apply rollback; reconcile retries. |
| `src/fam_os/adapters/shell/natural_engineering.py` | Required recovery approval and truthful result wording. |
| `src/fam_os/console/static/natural_engineering.js` | Conversation recovery checkpoint and no-commit result. |
| `src/fam_os/adapters/sqlite/engineering_incident.py` | Stable incident and receipt lifecycle ordering. |
| `tests/integration/test_natural_engineering_incident.py` | Apply-fail-rollback-close and retry integration. |
| `tests/unit/test_local_git_delivery_service.py` | Exact head binding and drift denial. |
| `tests/unit/test_fam_shell_natural_engineering.py` | Same-owner Shell recovery checkpoint. |

## Public interfaces

- `LocalGitDeliveryService.precommit_rollback_preview(...)`
- `LocalGitDeliveryService.require_precommit_rollback_head(...)`
- `LocalGitDeliveryService.has_committed_delivery(...)`
- Natural task outcome `postapply_verification_failed` may now include
  `rollback_checkpoint` and `incident_evidence`.
- A successful pre-commit rollback returns `rollback_completed` without
  `git_rollback_delivery`.

## Validation

```bash
larry run env PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_engineering_incident_service \
  tests.unit.test_local_git_delivery_service \
  tests.unit.test_candidate_changeset_service \
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

Result: 82 tests passed. Raw log:
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T09-55-51-835Z.log`.

```bash
larry run env PYTHONPATH=src:. python3 -m unittest discover \
  -s tests/architecture -t .
```

Result: 41 architecture tests passed. Raw log:
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T09-55-51-827Z.log`.

```bash
larry run env PYTHONPATH=src:. python3 tools/render_contract_schemas.py
node --check src/fam_os/console/static/natural_engineering.js
git diff --check
```

Result: all 408 schema artifacts rendered and validated; JavaScript syntax and
diff whitespace checks passed.

## Evidence and artifacts

- ADR 0213
- The source validation logs above
- The real Git repository and owner-workspace assertions in
  `tests/integration/test_natural_engineering_incident.py`

## Known limitations and risks

- Console presentation has syntax and HTTP asset coverage but not a browser DOM
  interaction fixture for this new state; the real natural API and Shell paths
  are directly exercised.
- A task interrupted after apply but before reverification has no failure
  incident yet; automatic verifier resumption remains required.
- These source changes postdate signed candidate
  `phase30-governance-20260719-3`; that installation does not prove them.

## Operational notes

No live service, active release, owner repository outside tests, remote, or host
policy was changed. Test repositories were temporary and removed automatically.

## Recommended next entry point

Add bounded verification-driven repair under the existing monotonic task budget:
create a typed remediation proposal, replace the failed candidate state safely,
run signed verification, and record repeated monitored recovery before closure.
Then include both repaired and rollback branches in the next signed candidate.
