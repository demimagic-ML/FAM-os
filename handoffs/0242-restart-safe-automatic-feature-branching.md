# Handoff 0242: Restart-safe automatic feature branching

**Date:** 2026-07-19  
**Plan step:** Phase 30.1 and 29.7  
**Status:** Partial  
**Previous handoff:** `0241-natural-failure-incident-attachment.md`

## Objective

Remove manual feature-branch preparation from the natural push/PR lifecycle
without granting protected-ref mutation or weakening restart reconciliation.

## Scope completed

- Derive a stable task-specific `fam/...` branch when local delivery begins on
  a protected branch.
- Persist the exact branch action before effect inside the local Git delivery
  record.
- Require a fresh live modify authorization for branch creation.
- Reconcile an interruption after branch creation only from the exact branch
  and unchanged head object.
- Stop on an existing derived-branch collision without committing to the
  protected ref.
- Preserve an already selected non-protected branch.
- Run the real natural publication integration from `main` through feature
  branch, verified local commit, separate publication grant, push, and draft PR
  receipt.

## Explicitly not completed

- Signed installed-product proof of automatic branching, rollback, publication,
  or incident controls.
- Fetch/review/merge/rebase/conflict/tag/release reconciliation from Phase 29.7.
- Multi-repository delivery from Phase 29.8.
- Remaining governance, operational powers, profile matrices, soak, and human
  review gates.

## Architecture and decisions

ADR 0208 places feature-branch creation in the durable local-delivery intent
rather than in UI or model output. The local branch consumes only the existing
task-scoped modify authority. Remote effects remain governed by ADR 0206.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/local_git_delivery.py` | Persist, authorize, execute, and reconcile automatic feature branching. |
| `src/fam_os/adapters/git/local.py` | Recognize an exact branch effect after interrupted receipt persistence. |
| `tests/unit/test_local_git_delivery_service.py` | Prove ordinary creation, crash reconciliation, and collision denial. |
| `tests/integration/test_natural_engineering_publication.py` | Prove the complete source path beginning on `main`. |
| `schemas/v1alpha1/fam.core.local-git-delivery.schema.json` | Render optional branch action and receipt fields. |

## Public interfaces

- `LocalGitDeliveryRecord.branch_action`
- `LocalGitDeliveryRecord.branch_receipt`
- `LocalGitPort.reconcile_branch(action)`

The existing local-delivery schema root remains
`fam.core.local-git-delivery/v1alpha1`; new fields are optional so persisted
pre-branch records remain decodable.

## Validation

```bash
larry run env PYTHONPATH=src:. python3 tools/render_contract_schemas.py
larry run env PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_local_git_delivery_service \
  tests.integration.test_natural_engineering_checkpoint \
  tests.integration.test_natural_engineering_publication \
  tests.unit.test_git_delivery \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references
git diff --check
```

Result: 406 schemas rendered; 45 tests passed in 1.812 seconds; diff check
passed. A further direct branch/publication run passed 5 tests in 0.545 seconds.

## Evidence and artifacts

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T08-56-34-857Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T08-57-04-155Z.log`
- `docs/decisions/0208-protected-local-refs-derive-an-exact-feature-branch.md`

## Known limitations and risks

- The derived branch is intentionally not reused. A prior branch with the same
  task identity requires explicit reconciliation, which belongs to Phase 29.7.
- The branch action is visible in the local-delivery receipt after the effect;
  the later publication checkpoint displays the exact source/target ref before
  any remote effect.
- This checkout remains source-only and heavily changed; no active release or
  live process was altered.

## Operational notes

No service was restarted, no remote outside the isolated test bare repository
was contacted, and the active installation at `127.0.0.1:8765` was not changed.

## Recommended next entry point

Build a clean signed candidate containing Handoffs 0239–0242 and prove the
ordinary main-branch natural path from its installed Console and Shell. If host
policy still blocks verifier execution, preserve the fail-closed result and
continue source composition of Phases 30.6–30.8 without weakening it.
