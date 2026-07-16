# Handoff 0035: Bounded repair and escalation transitions

**Date:** 2026-07-16  
**Plan step:** Phase 4.6  
**Status:** Complete  
**Previous handoff:** `0034-core-confirmation-transitions.md`

## Objective

Make repair and escalation finite, reviewed state transitions with atomic budget
and attempt-identity protection, while retaining failed candidates only as
non-releasing references and invoking no experts.

## Scope completed

- Required planned capabilities to exactly equal routed capabilities.
- Added trusted per-plan repair/escalation step classification and ceilings.
- Allowed attempts only through declared failed edges into distinct unrolled
  inference steps.
- Derived budget consumption from immutable accepted event history.
- Added atomic paired reservation for failed and next-attempt IDs across plans.
- Persisted failed/repair/escalation references without candidate content.
- Added budget, replay, staleness, classification, and architecture tests.

## Explicitly not completed

- Expert or verifier invocation.
- Candidate, prompt, exception, or verifier-payload persistence.
- Token, time, energy, or hardware attempt budgets.
- Cancellation, timeout, degradation, or final result assembly.

## Architecture and decisions

ADR 0036 selects unrolled acyclic plan steps plus a stricter trusted policy
ceiling. Plan compare-and-set is atomic budget consumption; concurrent losers
cannot alter state, though their attempt IDs remain consumed. Provider code has
no role in choosing targets or limits.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/contracts/plan.py` | Require exact routed/planned capability closure. |
| `src/fam_os/core/lifecycle/attempt_contracts.py` | Define policies, commands, kinds, rejections, and results. |
| `src/fam_os/core/lifecycle/attempt_ports.py` | Define trusted policy and replay ports. |
| `src/fam_os/core/lifecycle/attempt_registry.py` | Provide in-memory policy lookup and atomic paired replay reservation. |
| `src/fam_os/core/lifecycle/attempt_service.py` | Classify, budget, reserve, reference, and transition attempts. |
| `src/fam_os/core/lifecycle/contracts.py` | Add failed/repair/escalation evidence kinds and validation. |
| `src/fam_os/core/lifecycle/__init__.py` | Export attempt lifecycle interfaces. |
| `tests/unit/test_core_attempt_transitions.py` | Prove repair/escalation, budgets, replay, and staleness. |
| `tests/architecture/test_core_attempt_boundary.py` | Prevent candidate/provider dependencies. |
| `docs/protocols/CORE_ATTEMPT_TRANSITIONS.md` | Document bounds and evidence semantics. |
| `docs/decisions/0036-unrolled-budgeted-attempt-transitions.md` | Record the durable attempt decision. |
| `src/fam_os/core/README.md` | Update Core ownership. |
| `README.md` | Update implementation status. |
| `MASTER_PLAN.md` | Complete Phase 4.6 and select Phase 4.7. |

## Public interfaces

- Added `AttemptBudgetPolicy`, `AttemptKind`, `AttemptRejection`,
  `AttemptTransitionCommand`, and `AttemptTransitionResult`.
- Added `AttemptPolicyRegistry`, `AttemptReplayRegistry`, and in-memory
  implementations.
- Added `AttemptTransitionService.transition_after_failure`.
- Added `PlanEvidenceKind.FAILED_ATTEMPT`, `REPAIR_ATTEMPT`, and
  `ESCALATION_ATTEMPT`.

## Validation

```bash
PYTHONPATH=src python3 -m unittest tests.unit.test_core_attempt_transitions tests.architecture.test_core_attempt_boundary
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
# Parse src/ and tools/ with ast; fail for modules >=300 or functions >=50 lines.
larry index .
larry health .
```

Result: 6 focused tests passed; the full suite passed 385 tests; all 35 schema
artifacts matched; compilation passed; the AST size policy was clean; Larry
indexed 527 files and 1,445 symbols with clean freshness/verification; the
persisted code graph contains 7,541 nodes and 24,877 edges.

## Evidence and artifacts

- `docs/protocols/CORE_ATTEMPT_TRANSITIONS.md`
- `docs/decisions/0036-unrolled-budgeted-attempt-transitions.md`
- `tests/unit/test_core_attempt_transitions.py`
- `tests/architecture/test_core_attempt_boundary.py`

## Known limitations and risks

- Policy, replay, and plan state are process-local.
- Lost-race attempt IDs are consumed and require replacement.
- Only attempt counts are bounded; resource budgets remain future work.
- Failed references have no durable evidence object store yet.

## Operational notes

No model, expert, verifier, service, port, machine configuration, or credential
changed.

## Recommended next entry point

Begin Phase 4.7. Add typed cancellation/deadline/degradation commands bound to
the exact instance and revision. Require explicit `cancelled` or `unavailable`
edges, use replay-safe control-event IDs, make terminals absorbing/idempotent,
and retain bounded degradation evidence without continuing into action execution
or final result release.
