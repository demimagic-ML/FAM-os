# Handoff 0033: Authorized Core observation and action-proposal steps

**Date:** 2026-07-16  
**Plan step:** Phase 4.4  
**Status:** Complete  
**Previous handoff:** `0032-core-plan-state-machine.md`

## Objective

Allow the generic Core plan lifecycle to acquire authorized application
observations and action proposals through fake-friendly ports while keeping
observation, proposal, modification, and execution authority separate.

## Scope completed

- Added original admission ID and expiry binding to plan state.
- Added exact Core permission, Application grant, subject, authority, capability,
  instance, application, and resource-scope checks before provider access.
- Added narrow capability/observation/action-preparation provider ports with no
  action execution method.
- Added distinct transient commands for observation and action proposal.
- Validated returned request identity, observation resource, proposal policy,
  reversibility, confirmation, and postconditions.
- Mapped observation statuses to declared typed plan outcomes.
- Persisted only typed evidence reference ID, kind, and capability in plan events.
- Advanced valid action proposals to `CONFIRM_ACTION`, never directly to effect.
- Added adversarial, expiry, scope, authority, provider-failure, and architecture
  tests.

## Explicitly not completed

- User approval or denial recording.
- Action modification/execution, reversal, or postcondition verification.
- Durable evidence-object storage.
- Real connector registry, MCP, VS Code extension, or authenticated transport.
- Generic permission-expiry transitions outside application-backed steps.

## Architecture and decisions

ADR 0034 selects a least-authority application evidence port and records that
`OBSERVE`, `PROPOSE`, `MODIFY`, and `EXECUTE` are distinct powers. A plan snapshot
stores an opaque admission ID and original expiry, but no principal/session/prompt,
so a new routed object cannot silently refresh stale authority. Raw observations
and previews remain transient; the state log stores bounded references only.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/lifecycle/application_contracts.py` | Define transient acquisition commands and one-of step results. |
| `src/fam_os/core/lifecycle/application_ports.py` | Define capability/evidence and permission-registry ports without execution. |
| `src/fam_os/core/lifecycle/application_service.py` | Authorize, call, validate, reference, and advance application steps. |
| `src/fam_os/core/lifecycle/contracts.py` | Add opaque authority binding and typed evidence references with replay checks. |
| `src/fam_os/core/lifecycle/service.py` | Persist authority binding and evidence-bearing transitions. |
| `src/fam_os/core/lifecycle/repository.py` | Preserve authority binding across atomic replacement. |
| `src/fam_os/core/lifecycle/__init__.py` | Export the new Core lifecycle surface. |
| `tests/unit/test_core_application_steps.py` | Prove authorization, evidence, separation, and failure behavior. |
| `tests/architecture/test_core_application_step_boundary.py` | Prevent runtime/provider boundary imports. |
| `tests/architecture/test_core_plan_lifecycle_boundary.py` | Keep the generic state machine provider-independent. |
| `tests/unit/test_core_plan_lifecycle.py` | Preserve authority binding in forged-history coverage. |
| `docs/protocols/CORE_APPLICATION_STEPS.md` | Document authorization sequence and evidence policy. |
| `docs/protocols/CORE_PLAN_LIFECYCLE.md` | Document minimal original-admission binding. |
| `docs/decisions/0034-separate-observation-proposal-and-execution-authority.md` | Record the durable authority decision. |
| `src/fam_os/core/README.md` | Update Core ownership. |
| `README.md` | Update current implementation status. |
| `MASTER_PLAN.md` | Complete Phase 4.4 and select Phase 4.5. |

## Public interfaces

- Added `PlanAuthorityBinding`, `PlanEvidenceKind`, and
  `PlanEvidenceReference`.
- Extended `PlanLifecycleEvent` with typed evidence references.
- Added `ObservationAcquisition`, `ActionProposalAcquisition`,
  `ApplicationStepResult`, and `ApplicationStepRejection`.
- Added `ApplicationEvidenceProvider` and `ApplicationPermissionRegistry`.
- Added `ApplicationStepService.acquire_observation` and
  `ApplicationStepService.acquire_action_proposal`.

## Validation

```bash
PYTHONPATH=src python3 -m unittest tests.unit.test_core_application_steps tests.architecture.test_core_application_step_boundary
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
# Parse src/ and tools/ with ast; fail for modules >=300 or functions >=50 lines.
larry index .
larry health .
```

Result: 10 focused tests passed; the full suite passed 370 tests; all 35 schema
artifacts matched; compilation passed; the AST size policy was clean; Larry
indexed 509 files and 1,391 symbols with clean freshness/verification; the
persisted code graph contains 7,392 nodes and 23,819 edges.

## Evidence and artifacts

- `docs/protocols/CORE_APPLICATION_STEPS.md`
- `docs/decisions/0034-separate-observation-proposal-and-execution-authority.md`
- `tests/unit/test_core_application_steps.py`
- `tests/architecture/test_core_application_step_boundary.py`

## Known limitations and risks

- Referenced observations/proposals have no durable evidence store yet; callers
  must not assume a reference survives process restart.
- Permission rejection before provider access is not yet a persisted transition.
- Provider calls can complete just before a concurrent plan transition wins; the
  evidence is then discarded and no effect has occurred.
- Resource-scope matching is exact URI equality in this phase; hierarchical
  scope semantics require an explicit future policy.

## Operational notes

No applications, services, models, ports, machine configuration, or credentials
changed. All provider behavior is fake and in-process.

## Recommended next entry point

Begin Phase 4.5 in `core/lifecycle`. Read `ActionConfirmation`, confirmation
policy, ADR 0034, and the latest plan event evidence reference. Bind a confirmation
to the current proposal reference, permission grant, principal, plan instance,
and revision. Persist approved, denied, and expired outcomes without calling an
action-execution method. Reject cross-plan and replayed confirmation.
