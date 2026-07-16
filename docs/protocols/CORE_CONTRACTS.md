# Core Request, Routing, Plan, and Result Contracts

## Contract families

| Family | Python version marker | Owner |
|---|---|---|
| Core request, execution plan, and final result | `fam.core/v1alpha1` | `fam_os.core.contracts` |
| Routing request and result | `fam.routing/v1alpha1` | `fam_os.routing` |
| Application capability and connector boundary | `fam.applications/v1alpha1` | `fam_os.applications` |

These markers identify the current Python domain-contract generations. Their strict self-describing JSON roots, generated Draft 2020-12 schemas, exact alpha compatibility, and decoder policy are defined in `SERIALIZED_SCHEMA_COMPATIBILITY.md` and ADR 0018.

## Request

`TaskRequest` is the provider-neutral input admitted by FAM Core. It contains:

- Stable request identity.
- User intent as prompt text.
- Required capability identifiers.
- Whether verified release is required.
- Core contract-family version.

Required capabilities are normalized, unique, strictly bounded identifiers. Phase
4.1 keeps user/session identity outside caller-authored task content and binds it
through trusted authority lookup into an immutable least-privilege permission
context. See `CORE_REQUEST_ADMISSION.md`. Deadlines, cancellation, and permission
expiry during execution remain later Phase 4 concerns.

## Routing

`RoutingRequest` carries the request identity, prompt, required capabilities, and routing contract version. `RouteDecision` reports the route, bounded confidence, reason, and normalized required capabilities. `RoutingResult` combines the decision with optional provider-neutral inference metrics.

Phase 4.2 constructs this request only from an admitted request and its effective
permission context. Returned capabilities must match exactly, and router failures
are mapped to structured Core evidence. See `CORE_ROUTING_LIFECYCLE.md`.

The Phase 1 route names remain `kernel`, `code`, `math`, and `retrieval`. Route expansion is additive and must not introduce model-provider identities into routing contracts.

## Execution plan

`ExecutionPlan` is a deterministic, immutable, provider-neutral transition graph.

It contains:

- Plan and request identity.
- The accepted route decision.
- One entry step.
- Typed steps.
- Outcome-selected transitions.
- Whether release requires verification.
- Core contract-family version.

### Step kinds

- `observe`
- `inference`
- `deterministic_tool`
- `prepare_action`
- `confirm_action`
- `execute_action`
- `verify`
- `finalize`

Steps name required capabilities and deterministic acceptance checks rather than model names, application SDK objects, commands, or provider payloads.

### Transition outcomes

- `succeeded`
- `failed`
- `denied`
- `unavailable`
- `cancelled`
- `expired`

Each `(source step, outcome)` pair selects at most one target. This keeps execution deterministic while allowing bounded repair, escalation, approval, denial, and degradation branches to be unrolled explicitly.

`expired` distinguishes permission or grant expiry from explicit user denial.
Phase 4.5 requires a reviewed expiry edge and records bounded expiry evidence;
see `CORE_CONFIRMATION_TRANSITIONS.md`.

### Terminal dispositions

- `release`
- `withhold`
- `fail`

Every plan has a reachable release terminal with an inbound transition. If `verification_required` is true, every transition into a release terminal must be a successful transition from a step declaring deterministic acceptance checks. Non-verified conversational work may release after normal successful work without inventing false verification evidence.

### Construction invariants

- Step identifiers are unique.
- Every transition references known steps.
- A step outcome has at most one target.
- Final steps have no outgoing transitions.
- Non-final steps have at least one outgoing transition.
- Every step is reachable from the entry.
- The graph is acyclic; bounded retries are represented as separate steps rather than loops.
- Every capability required by routing appears in at least one plan step.
- Observation, inference, tool, prepared-action, confirmation, and executed-action steps identify capabilities.
- Verification and executed-action steps identify acceptance checks.
- Finalization never executes capabilities or acceptance checks.

Phase 4.3 implements the first generic runtime over this safe plan: exact route
binding, immutable in-memory snapshots, append-only replay-validated events,
optimistic revision checks, declared-edge-only transitions, and terminal states.
It does not execute providers yet. See `CORE_PLAN_LIFECYCLE.md`. Cancellation,
permission rechecks, provider evidence, and durable recovery remain later work.

## Final result

`TaskResult` remains the only Core result intended to cross the user-visible release boundary.

- `completed` carries content for work that does not claim verification.
- `verified` carries content and one or more evidence identifiers.
- `withheld` carries no content and includes a reason.
- `failed` carries no content and includes a reason.

The optional `plan_id` links a future result to its execution plan. `evidence_ids` link verified content to trusted evidence. Phase 1 verified-code orchestration now records the final passing verification identifier, and `VerifiedExecutionOutcome` checks that the released candidate and evidence both come from the final passing attempt.

Failed results now carry a `fam.failure/v1alpha1` structured failure, and released results may carry explicit non-withholding degradation notices. Safe messages, evidence linking, retry policy, and withholding rules are documented in `FAILURE_DEGRADATION_CONTRACTS.md` and ADR 0017.

## Phase 1 compatibility

The existing verified code use case still performs route, economical attempt, bounded repair, escalation, verification, and passing-candidate-only release. The contract change does not insert a new plan executor into that proven path. Instead, tests express the same bounded flow as an `ExecutionPlan`, while the Phase 1 use case continues to run until Phase 4 deliberately adopts the generic state machine.

This separation avoids silently replacing measured behavior while still making the future lifecycle explicit.
