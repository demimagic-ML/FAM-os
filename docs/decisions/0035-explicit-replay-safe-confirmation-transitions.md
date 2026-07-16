# ADR 0035: Use explicit replay-safe confirmation and expiry transitions

**Status:** Accepted  
**Date:** 2026-07-16

## Context

An action proposal is not permission to execute. Core must distinguish approval,
denial, and permission expiry; bind a decision to exactly one proposal and plan
revision; and prevent the same user decision from being replayed across plans.
The existing transition vocabulary had no explicit expiry outcome.

## Decision

Add `expired` to `StepOutcome` and the strict execution-plan schema. Require a
reviewed plan edge for approval (`succeeded`), denial (`denied`), and expiry
(`expired`).

Persist permission-grant identity in bounded plan evidence references. Bind
confirmation to the current proposal reference, grant, admitted principal,
capability, proposal time, plan instance, route context, and optimistic revision.

Reserve confirmation IDs through an atomic replay-registry port after validation
and before state mutation. Record missing, expired, or revoked permission through
an explicit expiry transition. Keep confirmation policy independent from action
execution and provider adapters.

## Consequences

- Approval cannot be applied to another proposal, grant, principal, or plan
  revision.
- One confirmation ID cannot authorize multiple plan instances.
- Expiry is distinguishable from explicit user denial in persisted history.
- Stale decisions cannot silently execute after permission loss.
- A confirmation may be consumed if it loses a final compare-and-set race; this
  favors non-replay over automatic reuse.
- Execution-plan schema artifacts gain the additive `expired` enum value while
  retaining the current alpha family version.

## Alternatives considered

1. Map expiry to `denied`: rejected because it loses whether the user denied or
   authority lapsed.
2. Trust proposal ID without grant/principal binding: rejected because proposal
   identifiers are not permission.
3. Store full action proposals and confirmations in plan events: rejected because
   bounded references are sufficient for transition history.
4. Make replay protection local to one plan: rejected because the same
   confirmation could authorize a second plan.
5. Execute immediately after approval: rejected because modification/execution
   and postcondition verification are later, separate authorities.

## Evidence

- `src/fam_os/core/lifecycle/confirmation_contracts.py`
- `src/fam_os/core/lifecycle/confirmation_ports.py`
- `src/fam_os/core/lifecycle/confirmation_registry.py`
- `src/fam_os/core/lifecycle/confirmation_service.py`
- `tests/unit/test_core_confirmation_transitions.py`
- `tests/architecture/test_core_confirmation_boundary.py`
- `docs/protocols/CORE_CONFIRMATION_TRANSITIONS.md`
