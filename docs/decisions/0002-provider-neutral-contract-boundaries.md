# ADR 0002: Provider-neutral contract boundaries

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The RNF prototype proved routing, constrained activation, deterministic verification, repair, and escalation. Its experiment modules also mix domain decisions with Ollama HTTP, Linux commands, cgroup files, reporting, and prompts. Copying those modules would make FAM_OS depend on the first prototype mechanism.

## Decision

FAM_OS begins migration with small typed contracts owned by the component whose language they represent:

- Core owns task requests, terminal results, and application ports.
- Routing owns route decisions.
- Experts owns expert identity, tier, capabilities, and lifecycle language.
- Scheduler owns resource budgets and placement plans.
- Verification owns deterministic verdicts.
- Telemetry owns provider-neutral measurements.

The inference runtime is an application port. Ollama will be one adapter implementing that port; its URL and response shape are not domain fields. Contracts use immutable standard-library dataclasses and enums so Phase 1 has no validation-framework or inference-provider dependency.

Final-result contracts enforce the first release invariant: a withheld or failed candidate cannot carry user-visible content, and verified content must have an explicit verified status.

## Consequences

- Prototype behavior can migrate one component at a time.
- Ollama, systemd, and Linux details remain replaceable.
- Invalid confidence, budgets, manifests, and release states fail at construction.
- Phase 2 can version serialized schemas without making Phase 1 runtime code depend on a specific schema library.
- Contract changes require focused tests and a later ADR when compatibility policy is introduced.

## Alternatives considered

1. Move prototype modules unchanged and refactor later: rejected because it preserves coupling at the new project boundary.
2. Put every type in one global contracts module: rejected because ownership and dependency direction would become ambiguous.
3. Adopt a third-party validation library immediately: deferred until versioned external schemas are designed in Phase 2.

## Evidence

- `docs/migration/PROTOTYPE_MIGRATION_MAP.md` identifies the prototype coupling and destination owners.
- Unit tests construct the initial contracts and enforce release, routing, resource, and verification invariants.
- The inference port contains no Ollama URL or provider response type.

