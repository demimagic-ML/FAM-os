# Core confirmation, denial, and permission-expiry transitions

## Boundary

Phase 4.5 consumes a previously persisted `action_proposal` reference while the
plan is at `CONFIRM_ACTION`. It records approved, denied, or expired. This phase
records authority evidence and advances the reviewed plan. It does not call an
application connector or execute an action.

## Proposal binding

The immediately preceding transition into `CONFIRM_ACTION` must contain exactly
one action-proposal reference for the current step capability. That bounded
reference carries proposal/reference ID, evidence kind, capability ID, and
permission-grant ID.

A user confirmation must match the proposal ID and grant ID exactly. It must be
decided by the admitted principal, at or after proposal creation, and no later
than Core's current trusted clock. The original Core admission ID, route,
capabilities, and expiry must still match the plan snapshot.

The authoritative Application Fabric grant must still belong to that principal,
include `PROPOSE`, and be active both at processing time and at the recorded
decision time.

## Outcomes

| Condition | Plan outcome | Persisted evidence kind |
|---|---|---|
| Approved confirmation | `succeeded` | `action_confirmation` |
| Denied confirmation | `denied` | `action_confirmation` |
| Core permission expired | `expired` | `permission_expiry` |
| Application grant missing, expired, or revoked | `expired` | `permission_expiry` |

`expired` is a first-class `StepOutcome` in the generated execution-plan schema.
Plans must declare the expired edge explicitly; Core never substitutes a denial
or invents a target.

An explicit expiry command refuses to transition while both permissions remain
active. A confirmation arriving after expiry records the expiry transition
instead of accepting a decision made under stale authority.

## Replay and concurrency

Confirmation IDs are reserved atomically in a `ConfirmationReplayRegistry`
after deterministic validation and edge checks. One confirmation cannot be
accepted twice in one plan or reused across two plans sharing the registry.

Plan revision compare-and-set remains the final state mutation guard. A stale
confirmation is rejected before replay reservation, so it may still be submitted
against the correct current revision. If a concurrent state change wins after
reservation, the confirmation remains consumed; callers must request new
confirmation rather than risk replaying stale user intent.

## Evidence privacy

Plan events retain only confirmation or expiry reference ID, kind, capability,
and permission-grant ID. They do not persist the action preview, prompt,
principal, reason text, connector session, or provider payload. The typed
`ActionConfirmation` is returned transiently on approved or denied success.

## Current limitations

- Confirmation and plan repositories are in-memory and process-local.
- There is no durable trusted user-presence or authentication transport yet.
- Confirmation policy is represented by the reviewed `CONFIRM_ACTION` step; the
  real Application Fabric must construct that step from proposal policy.
- Approved state is not execution authority. Phase 4.5 exposes no action
  execution method.
