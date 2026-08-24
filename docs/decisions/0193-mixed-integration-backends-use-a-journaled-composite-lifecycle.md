# ADR 0193: Mixed integration backends use a journaled composite lifecycle

Status: Accepted

## Context

Docker and process/API/browser adapters already provided bounded homogeneous
environments, but the provider-neutral router rejected every plan containing
both families. Simply launching two subplans would duplicate aggregate resource
limits, lose dependency order, capture retained artifacts twice, and make
partial cleanup impossible to resume safely after restart.

## Decision

When and only when both concrete adapters are composed, the router selects a
mixed adapter for plans spanning container and process families. The adapter
derives a backend dependency graph from immutable service dependencies. It
launches backend groups in topological order and cleans them in reverse order.
Dependencies already satisfied by another backend are removed only from the
private subplan; the admitted owner plan and its digest are unchanged.

Memory, CPU, and process limits are deterministically partitioned by service
count and sum exactly to the admitted aggregate limits. The concrete adapters
therefore cannot each consume the full plan budget. Required authorities are
recomputed exactly for each private subplan. Network policy, host identity,
permit identity, image digests, recipe signatures, and secret references remain
subject to their existing concrete checks.

An owner-private mode-0600 composite journal records exact backend order,
successful launches, cleanup evidence per backend, and terminal state. Launch
failure compensates previously launched groups in reverse order. Explicit
cleanup continues across backend failures and records every successful branch;
a later cleanup or restart reconciliation skips only evidence-backed completed
branches and resumes the remainder. Retained artifacts are captured exactly
once after all backends are terminal. Combined receipts preserve admitted
service order and exact backend cleanup evidence.

A backend-level dependency cycle is denied even when the service DAG itself is
acyclic, because satisfying it would require unsupported backend interleaving.
Mixed plans remain denied if either executor is absent.

## Consequences

- Product composition gains production-reachable mixed Docker plus process/API
  environments without exposing provider knowledge to Core.
- A real installed test proves a digest-pinned container dependency becomes
  healthy before a signed-recipe API, then a fresh adapter instance reconciles
  and removes both runtime families.
- Journal tampering, absent backends, backend-group cycles, launch failure, and
  partial cleanup have deliberate negative coverage.
- Backend grouping currently provides dependency readiness ordering, not a
  shared cross-backend service network. Docker and process isolation policies
  remain independent.
- If launch compensation itself fails before Product persists a successful
  start result, the candidate journal records `cleanup_required`, but product
  startup does not yet discover that orphan automatically. This remains an
  explicit gate before an all-crash-points guarantee.
- Mixed Docker-process-Docker interleaving, allowlisted egress, portable browser
  packaging, independently enforced physical profiles, soak, and review remain
  open.

## Alternatives considered

- Give each backend the original full plan: rejected because limits would be
  duplicated and homogeneous adapters reject foreign service kinds.
- Run both backends concurrently: rejected because it violates dependency
  readiness and makes deterministic compensation harder.
- Store no composite state: rejected because partial cleanup could not resume
  without replaying already terminal effects.

## Evidence

- `src/fam_os/adapters/integration/composite_environment.py`
- `src/fam_os/adapters/integration/composite_state.py`
- `src/fam_os/adapters/integration/environment_router.py`
- `tests/unit/test_mixed_integration_environment.py`
- `tests/integration/test_real_mixed_integration_environment.py`
- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt12.json`
