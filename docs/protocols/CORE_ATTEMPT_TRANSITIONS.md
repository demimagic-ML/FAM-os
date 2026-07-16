# Bounded repair and escalation transitions

## Invariant

Repair and escalation are not loops and are not provider-selected retries. They
are distinct, predeclared, reachable inference steps in the immutable acyclic
execution plan. A trusted `AttemptBudgetPolicy` classifies those step IDs and may
set limits lower than the number of unrolled steps.

## Transition

`AttemptTransitionService.transition_after_failure` accepts only the declared
`failed` edge from the current step. Its target must:

- be classified as repair or escalation by policy for that exact plan;
- be an inference step;
- declare exactly one capability;
- remain inside the admitted capability tuple.

The service counts accepted repair/escalation references already present in the
immutable event history. If the configured limit is exhausted, state does not
change. Final compare-and-set state replacement is the atomic budget-consumption
point, so concurrent reports cannot both consume one plan revision.

## Evidence and replay

Each accepted transition atomically reserves two globally replay-protected IDs:

- the failed attempt/candidate reference;
- the next repair or escalation attempt reference.

The plan event stores only those typed IDs and the target capability. It stores
no candidate content, prompt, model response, exception, or verifier payload.
Failed material therefore remains referenceable for telemetry but cannot become
released content through this state transition.

IDs that lose a final revision race remain consumed. This prevents uncertain
reuse; a caller must issue new attempt identities against current state.

## Capability hardening

`ExecutionPlan` now requires the set of all planned capabilities to equal the
routed capability set exactly. It may neither omit routed authority nor smuggle
an additional capability into a later repair/escalation step.

## Current limitations

- Policies, replay state, and plan state are in-memory.
- This phase records attempt identities but invokes no expert or verifier.
- Token, time, and hardware budgets are not yet part of the attempt policy.
- Attempt quality and candidate retrieval remain later provider/evidence work.
