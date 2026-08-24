# Handoff 0177: Production action restart reconciliation

**Date:** 2026-07-18  
**Plan step:** Phase 17.4 correction; Phase 23.3 prerequisite  
**Status:** Source implementation complete; installed candidate matrix pending  
**Previous handoff:** `0176-clean-built-artifact-profile-matrix.md`

## Objective

Audit the claimed restart-safe action boundary in the real installed service,
repair any production reachability gap, and prove that restart cannot reuse
mutation authority or retry an uncertain provider.

## Gap found

The durable `StartupActionReconciler` had no production caller. Its only inbound
callers were two unit tests. `LocalProductService._gateway()` composed the real
Application Fabric and returned `ProductionTaskGateway` without reconciling
`application_action_states`. The Phase 17.4 component existed, but the product
boundary that Phase 17 and Phase 23 depend on did not.

## Scope completed

- Added a production coordinator that runs before Shell, Application, MCP, and
  Console clients can start work.
- Synchronized durable action, application, plan, and audit state for pending,
  approved, invoking, uncertain, and reconciliation-required actions.
- Added explicit `recovery_required` application state and a Shell projection
  that blocks worker creation when outcome observation is inconclusive.
- Added fresh recovery approval at an already-current execute step without
  rewinding the immutable plan or weakening the plan-event schema.
- Bound fresh recovery confirmation to the exact durable action record through
  the approved-to-invoking transition; arbitrary recovery-prefixed IDs do not
  authorize execution.
- Added model-free postcondition reconstruction for owner-directory create and
  reversal operations, including device/inode reversal identity.
- Added deterministic, content-free recovery audit/result evidence and
  hash-chain-validated event lookup for crash-idempotent audit commit.
- Proved normal pending restart, discarded approved authority, approval denial,
  uncertain mutation recovery without provider retry, and inconclusive
  connector recovery without worker replay.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/application_restart.py` | Production cross-repository recovery coordinator and directory postcondition reconstruction |
| `src/fam_os/product/service.py` | Invoke recovery before returning the production gateway |
| `src/fam_os/core/production/application_contracts.py` | Explicit application recovery state |
| `src/fam_os/core/production/application_gateway.py` | Recovery approval and blocked-reconciliation Shell views |
| `src/fam_os/core/production/gateway.py` | Prevent worker start while application recovery blocks |
| `src/fam_os/core/lifecycle/confirmation_service.py` | Replay-safe fresh reapproval at the execute step |
| `src/fam_os/core/lifecycle/action_execution_validation.py` | Exact durable recovery-confirmation authorization |
| `src/fam_os/product/storage/action_repository.py` | Recovery approval predicates over encrypted action state |
| `src/fam_os/adapters/audit/application_jsonl.py` | Validated idempotent event lookup |
| `tests/integration/test_verified_directory_action.py` | Real service restart fault-window coverage |
| `tests/integration/test_product_application_action.py` | Unsupported provider remains blocked without replay |
| `tests/unit/test_application_action_audit.py` | Audit lookup and tamper regressions |

## Safety invariants

- Production startup never authorizes provider retry.
- A pre-restart confirmation cannot authorize post-restart execution.
- A recovery confirmation must be fresh, replay-protected, proposal-bound,
  grant-bound, owner-bound, time-valid, and exactly present in durable action
  state.
- Reconciliation-required state is visible and cannot spawn a worker.
- A reconstructed verified action must have independently passing declared
  postconditions and, for a reversible directory create, device/inode identity.
- Audit content remains free of prompts, paths, parameters, output, and reversal
  tokens.

## Validation

Focused source validation passed 49 tests covering action execution,
confirmation, durable repositories, schemas, audit integrity, service restart,
directory mutation/reversal, and unsupported connector recovery. Ruff and mypy
passed on the changed source boundary. The complete source suite then passed
1,263 tests with two declared environment skips.

## Explicitly not completed

- No source test is counted as the Phase 23.3 installed matrix.
- Generic VS Code/file postconditions cannot be reconstructed without live
  provider output and remain `recovery_required`; this is intentional safe
  behavior, not a completed outcome.
- Phase 21.7 and Phase 23.4–23.8 remain open.

## Recommended next entry point

Build the Phase 23.3 single-candidate installed scenario matrix. Its application
module must stop and restart the installed service at both approval and
post-mutation/pre-result fault windows, then prove fresh approval, no provider
retry, durable audit evidence, and the final action receipt from the same
candidate manifest digest used by the remaining scenarios.
