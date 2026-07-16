# ADR 0034: Separate observation, proposal, and execution authority in Core

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The generic plan state machine needs application evidence, but calling a broad
connector session directly would make observation, proposal, and execution easy
to conflate. A stale routed object could also be substituted to refresh expired
permission unless plan state retains a minimal binding to the original
admission. Raw editor contents and action previews should not be copied into the
plan event log.

## Decision

Add a narrow `ApplicationEvidenceProvider` port exposing capability lookup,
observation, and action preparation only. Require separate `OBSERVE` and
`PROPOSE` authorities before those calls. Do not expose action execution.

Persist an opaque admission ID and original permission expiry in
`PlanAuthorityBinding`; retain no principal, session, prompt, or authority
record. Every application step must match that binding and the complete routed
plan context.

Validate application grant subject, time, authority, application, instance,
capability, provider resource scope, and grant resource scope before access.
Persist only typed evidence references in plan events. Keep raw evidence
transient in the in-process step result.

## Consequences

- Observation authority cannot prepare or execute an action.
- Modify authority alone cannot generate a proposal; proposal authority is
  explicit.
- A valid proposal advances to the plan's next reviewed state, typically
  confirmation, without applying an effect.
- Expired Core authority cannot be refreshed by supplying replacement routed
  evidence with the same request and route.
- Plan history stays bounded and avoids raw application content.
- Durable evidence retrieval and real connector transport remain future work.

## Alternatives considered

1. Pass `ConnectorTransport` directly into Core: rejected because it includes an
   execution method beyond Phase 4.4 authority.
2. Treat action `MODIFY` authority as permission to prepare: rejected because
   proposal and modification are separate user powers.
3. Persist complete observations and proposals in events: rejected because raw
   application content is unnecessary for transition history.
4. Recheck only capability IDs: rejected because application, instance,
   resource, subject, time, and original admission binding all matter.
5. Trust a fresh routed object's expiry: rejected because it permits permission
   substitution.

## Evidence

- `src/fam_os/core/lifecycle/application_contracts.py`
- `src/fam_os/core/lifecycle/application_ports.py`
- `src/fam_os/core/lifecycle/application_service.py`
- `tests/unit/test_core_application_steps.py`
- `tests/architecture/test_core_application_step_boundary.py`
- `docs/protocols/CORE_APPLICATION_STEPS.md`
