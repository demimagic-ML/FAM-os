# Handoff 0252: Owner-workspace monitored recovery closure

**Date:** 2026-07-19  
**Plan step:** Phase 30.7, 30.1, and 30.9  
**Status:** Partial  
**Previous handoff:** `0251-policy-selected-signed-independent-review.md`

## Objective

Replace the repair branch's duplicated immediate recovery evidence with a
genuinely later observation of the applied owner workspace before incident
reporting and closure.

## Scope completed

- Candidate repair now records one signed recovery observation and leaves the
  incident durably `recovery_monitored` at changeset approval.
- Successful post-apply owner-workspace reverification records the second
  observation from distinct verification IDs.
- Report and closure occur only after both observations exist.
- Restart/retry resumes from one or two observations without creating a third.
- Successful natural responses expose the final incident and complete evidence
  chain after commit.
- The real documentation-aware repair integration now proves one candidate
  observation, later owner-workspace observation, report, closure, and distinct
  conclusions.

## Explicitly not completed

- Signed installed or live production-verifier evidence for the repaired and
  rollback incident branches.
- Host AppArmor policy installation, final qualification matrices, soak, or
  independent human review.
- Remaining Phase 27/29 engineering powers.

## Architecture and decisions

ADR 0217 makes the normal post-apply signed verifier the independent later
recovery observer. Incident state stays truthful at every checkpoint: repaired
candidate success is monitored recovery, while closure means the exact applied
owner result also passed.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/natural_engineering_incidents.py` | Record at most one recovery observation per phase and resume closure. |
| `src/fam_os/product/natural_engineering_api.py` | Feed successful post-apply verification into monitored recovery. |
| `tests/integration/test_natural_engineering_incident.py` | Prove delayed distinct observation and closure. |

## Public interfaces

- `NaturalEngineeringIncidentCoordinator.complete_task_recovery(...)`
- A repaired activation now reports incident stage `recovery_monitored`; the
  successful post-apply response reports `closed`.

## Validation

```bash
env PYTHONPATH=src:. python3 -m unittest \
  tests.integration.test_natural_engineering_incident \
  tests.unit.test_product_natural_engineering_api
env PYTHONPATH=src:. python3 -m unittest discover -s tests/architecture -t .
env PYTHONPATH=src:. python3 tools/render_contract_schemas.py
git diff --check
```

Result: eight focused tests passed. The combined governance suite then passed
76 affected tests and 41 architecture tests; all 413 schemas rendered,
JavaScript syntax passed, and `git diff --check` passed.

## Evidence and artifacts

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T11-00-02-184Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T11-02-15-422Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T11-02-37-700Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T11-02-38-651Z.log`
- `docs/decisions/0217-repair-recovery-closes-only-after-owner-workspace-reverification.md`

## Known limitations and risks

- An owner who withholds the repaired changeset leaves the incident monitored
  rather than closed by design.
- Installed candidate `phase30-governance-20260719-3` predates this behavior.
- The host production sandbox still fails closed until `fam-os-userns` is
  loaded by the owner.

## Operational notes

No running service, active release, host policy, owner repository, model,
remote, or credential was changed. Test repositories were temporary.

## Recommended next entry point

Run the combined governance suite, then begin attaching the remaining Phase 27
operational powers to the same task/grant/candidate/verification/checkpoint
lifecycle before freezing the next signed candidate.
