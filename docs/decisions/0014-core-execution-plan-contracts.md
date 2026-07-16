# ADR 0014: Versioned-alpha Core execution-plan contracts

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 1 created provider-neutral task, routing, verified-attempt, and final-result types, but the orchestration sequence remained encoded inside the verified-code use case. Phase 2.1 requires an explicit execution-plan contract that can later represent application observations, tools, confirmations, actions, verification, repair, escalation, cancellation, and degradation without depending on Ollama, VS Code, MCP, or one verifier.

A simple ordered list cannot represent bounded success/failure branches. A runtime state machine implemented now would prematurely enter Phase 4 and risk changing the measured Phase 1 path.

## Decision

Core request, execution-plan, and final-result Python contracts form `fam.core/v1alpha1`. Routing request/results form `fam.routing/v1alpha1`. These version markers are internal contract-family identifiers until Phase 2.7 defines serialized schemas.

`ExecutionPlan` is an immutable directed acyclic transition graph:

- Typed steps name capabilities and acceptance checks.
- Transitions select one target for each source/outcome pair.
- Final steps declare release, withhold, or fail disposition.
- All steps are reachable from one entry.
- Non-final steps have outgoing transitions and final steps have none.
- Routed capabilities must be covered by plan steps.
- Verified release branches require successful accepted evidence.
- Normal responses that do not require verification may release without false verification claims.
- Retries and escalation are unrolled as separate steps; cycles are invalid.

The contract defines plan shape only. Phase 4 owns mutable execution state, event handling, authorization, cancellation, transition evaluation, recovery, and result assembly.

`TaskResult` gains optional plan identity, evidence identifiers, and Core contract version. Verified results require evidence. Withheld and failed results require a reason and still cannot expose content.

The existing verified-code use case now attaches the final passing verification ID to a verified `TaskResult`, and `VerifiedExecutionOutcome` checks that reference. It does not yet execute the new generic plan.

## Consequences

- Route, capability, plan, and final-result boundaries are explicit before Phase 4.
- Bounded repair and escalation can be described without loops or provider names.
- Application action confirmation and denial have plan vocabulary without importing connector types into Core.
- Verified and ordinary release remain semantically distinct.
- Release safety is enforced both in plan construction and final-result construction.
- Phase 4 can implement the state machine against a stable domain shape.
- Phase 2.7 must serialize recursive plan structures and version compatibility explicitly.
- Existing measured orchestration remains in place until deliberately replaced and parity-tested.

## Alternatives considered

1. Keep orchestration only in use-case code: rejected because Phase 4 would have no explicit auditable plan boundary.
2. Use an ordered list of commands: rejected because failure, repair, denial, and degradation branches would remain implicit.
3. Allow graph cycles for retries: rejected because bounded attempts are clearer and safer as explicit nodes.
4. Implement the complete runtime state machine now: deferred to Phase 4.3 to keep Phase 2 contract-only.
5. Require deterministic verification for every conversational response: rejected because that would misrepresent ordinary unverified language output.
6. Put model references or shell commands in plan steps: rejected because expert selection and concrete adapters remain separate concerns.

## Evidence

- `docs/protocols/CORE_CONTRACTS.md` documents the families and invariants.
- `tests/unit/test_core_plan_contracts.py` represents the existing bounded verified-code flow and rejects cycles, unreachable steps, uncovered capabilities, and unsafe release paths.
- Existing verified-code tests prove passing evidence is linked without changing repair/escalation outcomes.
- The full FAM_OS suite passes after the stricter final-result invariants.
