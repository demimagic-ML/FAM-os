# ADR 0046: Start FAM Shell as an unprivileged terminal client

**Status:** Accepted  
**Date:** 2026-07-16  
**Plan step:** Phase 5.8

## Context

FAM_OS needs an interface through which a user can ask for work, control
context, understand plans and progress, approve risky actions, cancel work, and
see final results. Giving the UI model, routing, permission, connector, or
release authority would create a second policy engine and make later graphical
interfaces behave differently from the terminal.

## Decision

Build the first Shell as a color-free terminal client over one narrow,
versioned, peer-authenticated local Core protocol.

- Keep selected context as references and capability IDs, not ambient content.
- Use monotonic immutable session snapshots as the full presentation state.
- Bind decisions and cancellation to exact session revision and approval ID.
- Render only the terminal result that Core supplies through its release-safe
  `TaskResult`; do not expose candidates or provider exceptions.
- Keep Core lifecycle projection on the server side.
- Run the Shell as a separate unprivileged process over a private `0600` Unix
  socket with `SO_PEERCRED`, bounded strict frames, typed schemas, and response
  correlation.
- Use explicit refresh for MVP progress and a plain command vocabulary usable by
  keyboards and screen readers.
- Neutralize terminal control characters in every rendered field.
- Make future graphical Shell and Console clients use the same Core gateway and
  presentation contracts rather than owning separate policy.

## Consequences

The terminal can be installed and run independently from Core, and fake-driven
tests exercise the real process boundary without a model runtime. A compromised
or buggy Shell cannot directly call experts, connectors, supervisor operations,
or verification services through its public surface. Core still must provide a
production `ShellCoreGateway` composition; Phase 5.8 provides its contract,
projection, dispatcher, authenticated endpoint, and client.

Explicit refresh is less fluid than push events but keeps the initial client
deterministic and small. A later GUI may add bounded event subscription while
preserving snapshot revision semantics.

Same-UID peer authentication does not attest executable provenance or resist a
different process already running under that Unix account. Package trust,
sandboxing, and service composition remain separate controls.

## Alternatives rejected

- A UI that invokes Ollama, experts, or connectors directly bypasses Core policy.
- Rendering model progress tokens as trusted status permits UI spoofing and
  candidate leakage.
- A graphical-only first interface makes headless and accessibility validation
  harder and couples product behavior to one toolkit.
- Reusing MCP as the Shell's internal lifecycle protocol would not express the
  revision, approval, cancellation, and terminal-release invariants required by
  the product.
