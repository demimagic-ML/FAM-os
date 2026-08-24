# ADR 0152: Production action recovery precedes client service

Status: Accepted

## Context

Phase 17 defined durable action states and a no-replay restart policy, but the
`StartupActionReconciler` was called only by unit tests. The installed service
composed its Application Fabric and immediately exposed Shell and Console
clients. A durable action left at `approved`, `invoking`, or `uncertain` could
therefore be resumed by an ordinary worker without production reconciliation.

Approval recovery also cannot rewind an immutable execution plan. After the
original confirmation transition, the plan is already at `EXECUTE_ACTION`, even
though restart must discard the old mutation authority.

## Decision

`LocalProductService` runs `ApplicationRestartCoordinator` after durable Core
and Application Fabric composition and before any client server is started.
The coordinator synchronizes action, application, plan, and content-free audit
state.

- Prepared, awaiting, and approved actions become `awaiting_approval`; any old
  confirmation is removed. If the plan already reached `EXECUTE_ACTION`, the
  Shell presents the same deterministic preview as an explicit recovery
  reapproval.
- Recovery approvals use a new replay-protected confirmation ID. Execution
  accepts it only when the durable action repository binds that exact ID to the
  proposal during the `approved` to `invoking` handoff. No synthetic plan event
  is treated as a normal confirmation event.
- A recovery denial records a cancellation transition and never invokes the
  provider.
- Invoking, uncertain, and reconciliation-required actions enter an explicit
  `recovery_required` application state before clients are served. The
  coordinator may resolve them only by re-observing declared postconditions.
  It never calls `execute_action` and never authorizes provider retry.
- Owner-directory actions are currently reconstructable from independent path,
  existence, emptiness, device, and inode observation. Unsupported or
  unavailable postconditions remain visibly blocked for reconciliation.
- Reconstructed results receive deterministic action-result and audit IDs.
  Audit lookup validates the complete private hash chain, allowing restart
  after audit append but before plan commit without a duplicate event.

The plan-event v1alpha1 contract remains unchanged. Recovery approval is bound
by the durable action repository, while recovery outcome evidence remains a
normal `ACTION_RESULT` plus `ACTION_AUDIT` transition from the action step.

## Consequences

- An installed restart can no longer expose a mutation worker before durable
  action state has been classified.
- Prior approval is historical evidence only and cannot authorize execution
  after restart.
- A mutation that may already have happened is never retried merely because a
  provider response was lost.
- Directory recovery can still produce a verified, reversible receipt when
  device and inode identity are independently observed.
- Application actions whose postconditions cannot be reconstructed remain
  blocked instead of being reported complete or failed from inference.
- Phase 23.3 still requires the same scenarios from one installed release
  candidate; source integration tests are not final installed evidence.

## Alternatives considered

- Calling the existing action-only reconciler from service startup was rejected
  because it did not synchronize application, plan, audit, or Shell state.
- Rewinding the plan to `CONFIRM_ACTION` was rejected because durable plans are
  append-only and revisioned.
- Adding a recovery-confirmation event to the public plan schema was rejected
  because confirmation evidence is valid only from a confirmation step and the
  durable action record already provides the exact local authority boundary.
- Automatically retrying an idempotent-looking provider call was rejected
  because transport idempotency does not prove that the external mutation did
  or did not occur.

## Evidence

- `src/fam_os/product/application_restart.py`
- `src/fam_os/product/service.py`
- `src/fam_os/core/production/application_gateway.py`
- `src/fam_os/core/lifecycle/confirmation_service.py`
- `src/fam_os/core/lifecycle/action_execution_validation.py`
- `src/fam_os/adapters/audit/application_jsonl.py`
- `tests/integration/test_verified_directory_action.py`
- `tests/integration/test_product_application_action.py`
- `tests/unit/test_application_action_audit.py`

