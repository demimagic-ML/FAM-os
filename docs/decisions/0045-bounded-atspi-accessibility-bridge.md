# ADR 0045: Use a bounded provider-isolated AT-SPI bridge

**Status:** Accepted  
**Date:** 2026-07-16  
**Plan step:** Phase 5.7

## Context

FAM_OS must work with unmodified applications that do not expose native APIs,
MCP servers, or sufficient deterministic OS capabilities. Linux AT-SPI offers a
semantic application tree and actions, but its provider objects are mutable,
content-bearing, application-controlled, and unsafe to expose directly to Core
or models. Object paths can become stale and password widgets require strict
redaction.

## Decision

Use AT-SPI as an Application Fabric level-3 adapter behind the provider-neutral
`AccessibilityProvider` port.

- Keep GI and AT-SPI object handles inside the concrete Linux adapter.
- Return breadth-first snapshots bounded by node, depth, text, and action limits.
- Require explicit text observation; redact password-role names, descriptions,
  text, and actions at both provider and public-contract boundaries.
- Identify objects by process ID, child-index path, and a full SHA-256 identity
  fingerprint.
- Separate prepare from perform and resolve/revalidate immediately before both.
- Expose only a named action allowlist within the observation action bound.
- Declare actions irreversible and always-confirmed until a capability proves a
  real undo or compensation path.
- Treat provider invocation as raw evidence and require an independent
  postcondition before successful release.
- Return explicit unavailable state when GI, the bus, the process root, or an
  unambiguous root is absent.

## Consequences

Unmodified applications gain bounded semantic observation and controlled action
without making AT-SPI the internal Application Fabric model. Stale references,
forged action proposals, protected content, and unbounded traversal are rejected
conservatively. The bridge may refuse a valid action when an application changes
identity fields between observation and execution; this is intentional.

AT-SPI data remains untrusted and same-session isolation is not a hardened
security boundary. Application-specific semantics, reliable undo, and intended
outcome verification require higher-fidelity connectors or Phase 5.11 policy.

## Alternatives rejected

- Exposing raw AT-SPI handles or method indexes to models bypasses bounds and
  permission semantics.
- Persisting provider object handles across approval permits stale-object actions.
- Treating password widget names or values as normal accessibility content risks
  secret disclosure.
- Using screen capture and pointer/keyboard injection here would collapse the
  semantic accessibility tier into the more restricted Phase 5.10 fallback.
