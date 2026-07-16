# Authorized Core application steps

## Boundary

Phase 4.4 connects two generic plan step kinds to fake-friendly Application
Fabric ports:

- `OBSERVE` acquires one typed `ObservationResult`;
- `PREPARE_ACTION` acquires one typed `ActionProposal`.

It does not confirm, modify, execute, reverse, or verify an application action.
The Core-facing provider port deliberately exposes no execution method.

## Authorization sequence

Before any provider call, Core requires all of the following:

1. The plan instance exists, is nonterminal, and has the expected revision.
2. The supplied routed evidence matches the plan's request, complete route,
   ordered effective capabilities, opaque admission ID, and original expiry.
3. The original Core permission has not expired.
4. The current plan step is exactly `OBSERVE` or `PREPARE_ACTION` and declares
   exactly one capability for this provider call.
5. An available registry entry matches that application instance, capability,
   and expected observation/action kind.
6. A current Application Fabric grant belongs to the admitted principal and
   covers the application, instance, capability, and exact resource scope.
7. Observation has `OBSERVE` authority; proposal creation has `PROPOSE`
   authority.

An action descriptor may declare `MODIFY` as the authority required for its
eventual effect, but preparing its proposal requires separate `PROPOSE`
authority. Holding `MODIFY` alone does not authorize proposal generation, and
proposal generation does not authorize execution.

## Evidence handling

Core constructs `ObservationRequest` and `ActionPreparationRequest`; callers do
not pass provider request objects through the state machine. Returned evidence
must preserve the exact request identity. Successful observations also preserve
an explicitly requested resource URI.

Action proposals must preserve the entire preparation request and match the
registered capability's reversibility, confirmation policy, and ordered
postcondition declarations. A mismatched or malformed provider result cannot
advance the plan.

Raw observation payloads and action previews are transient values in
`ApplicationStepResult`. The persisted plan event contains only a bounded typed
`PlanEvidenceReference`:

- reference ID;
- evidence kind (`observation` or `action_proposal`);
- capability ID.

The event-log validator checks that the evidence kind matches the source step
kind and that its capability belongs to that step. It never persists document
text, selection contents, diffs, prompts, principal identity, or connector
sessions.

## State transitions

Observation statuses map to existing plan outcomes:

| Observation status | Plan outcome |
|---|---|
| `observed` | `succeeded` |
| `denied` | `denied` |
| `unavailable` | `unavailable` |
| `failed` | `failed` |

A valid action proposal produces `succeeded`. The reviewed plan chooses the next
state; the reference test plan advances to `CONFIRM_ACTION`, never directly to
execution. Missing plan edges, stale revisions, and concurrent winners are
rejected by the generic state machine.

Pre-call permission or context rejection does not invoke the provider and does
not mutate state. Provider exceptions become a fixed `provider_unavailable`
rejection without leaking raw exception text.

## Current limitations

- Provider evidence is returned transiently; a durable evidence object store is
  not yet implemented.
- Permission expiry and explicit denial are rejected before access but do not
  yet become persisted plan transitions; Phase 4.5 owns that policy.
- The Application Fabric registry and provider are fake/in-process ports; the
  authenticated local transport and dynamic registry remain Phase 5 work.
- No application action can execute in this step.

Phase 4.5 consumes the action-proposal reference at `CONFIRM_ACTION`; see
`CORE_CONFIRMATION_TRANSITIONS.md`.
