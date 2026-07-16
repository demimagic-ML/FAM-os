# ADR 0008: Verified code orchestration and release boundary

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The RNF prototype proves a useful execution sequence: route a request, ask an economical code expert, verify its candidate, perform bounded repair, optionally unload smaller resident models, escalate to a larger expert, verify again, and release only a passing candidate. Its `run_verified_task` function also mixes provider HTTP calls, prompt construction, route parsing, verification, eviction choices, transition state, metrics, persistence, and report serialization.

FAM_OS must preserve the proven sequence without making Core depend on Ollama, Python tests, Bubblewrap, or hard-coded model names. Scheduler policy must own context and eviction choices. Failed candidates must remain available as internal evidence without crossing the user-visible result boundary.

## Decision

Routing owns `RoutingRequest`, `RoutingResult`, `TaskRouter`, the routing prompt, deterministic route parsing, and `ModelTaskRouter`. The model-backed implementation uses only `InferenceRuntime` and returns provider-neutral metrics.

Experts own the `ExpertCatalog` lookup port. The scheduler owns `PlacementPlanner` and returns `PlacementPlan`, including context allocation and expert IDs to evict. Core's `PlacementExecutor` validates and executes that decision; it resolves every eviction before unloading any model and never invents an eviction itself.

Core splits verified execution into:

- Pure initial-generation and repair prompt builders.
- `AttemptExecutor`, which performs exactly one inference and one verification.
- `PlacementExecutor`, which executes a scheduler-selected placement.
- `VerifiedCodePolicy`, which supplies model-independent bounds and expert IDs as data.
- `VerifiedCodeExecution`, which coordinates route, economical attempt, repair, escalation, escalation repair, and terminal release transitions.
- `ExecutionAttempt` and `VerifiedExecutionOutcome`, which retain typed internal evidence.

Repair and escalation counts are bounded. A verifier `ERROR` halts immediately because infrastructure failure is not candidate feedback. A verifier `FAILED` may drive the configured repair or escalation path. Only a final `VerificationStatus.PASSED` creates a verified `TaskResult` with content. Exhausted candidates create a withheld result with no content; configuration or empty-generation errors create a failed result with no content.

Prompt text, persistence, and policy configuration remain outside runtime adapters. Trusted verifier definitions remain inside verification composition and are never supplied by the model or Core orchestration.

## Consequences

- The state sequence is testable with in-memory fakes and no Ollama, Bubblewrap, systemd, or hardware commands.
- Model runtime, routing policy, catalog, scheduler, and verifier implementations can be replaced independently.
- Eviction behavior is explicit and auditable as expert IDs plus runtime unload calls.
- Attempt candidates are internal evidence, while `TaskResult` remains the safe user-visible release object.
- Routing inference metrics and every expert attempt's metrics and verification report remain typed.
- The use case currently handles the code route only. Other route families require their own application policy or a later general execution-plan state machine.
- The placement context budget is consumed now; complete memory, swap, device, and service-lifecycle enforcement remains future scheduler and supervisor work.
- Persistence, external APIs, cancellation, wall/token budgets across attempts, and structured adapter-failure degradation remain later phases.

## Alternatives considered

1. Copy `run_verified_task`: rejected because it retains provider, policy, persistence, verification, and scheduling coupling.
2. Let Core choose model names and unload targets: rejected because expert identity and eviction are catalog and scheduler responsibilities.
3. Return the last candidate after retries are exhausted: rejected because generation is not proof of task success.
4. Repair after verifier infrastructure errors: rejected because verifier unavailability does not establish a defect the model can correct.
5. Put prompts and retry loops inside the Ollama adapter: rejected because they are application policy and must survive runtime replacement.
6. Build the complete Phase 4 lifecycle now: rejected because Phase 1.9 is a controlled migration of proven code behavior, not permission, cancellation, application-action, and degradation expansion.

## Evidence

- Fake-driven tests cover initial success, economical repair, escalation, escalation repair, exhausted failure, verifier error, unsupported route, empty generation, scheduler context propagation, and safe eviction resolution.
- Exhausted failure retains four failed candidates in internal attempts while the final `TaskResult.content` remains `None`.
- Existing FAM_OS and parent RNF suites continue to pass.
- Handoff 0008 records exact commands, counts, graph verification, limitations, and the Phase 1.10 entry point.
