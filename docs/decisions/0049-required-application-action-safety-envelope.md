# ADR 0049: Require one Core-owned safety envelope for application actions

**Status:** Accepted  
**Date:** 2026-07-16  
**Plan step:** Phase 5.11

## Context

Application Fabric actions now arrive through native, MCP, deterministic tool,
accessibility, and screen/input adapters. Each adapter can preserve useful
provider semantics, but adapter-specific success cannot prove current authority,
user approval, or the requested semantic outcome. Divergent per-adapter safety
logic would create bypasses and inconsistent recovery behavior.

## Decision

Require one Core execution service to bind the admitted request and current plan
revision to the live capability, scoped grant, exact proposal, prior proposal and
approval evidence, approving principal, trusted time, and declared conditions.

The service must:

- append a privacy-bounded durable request audit before invocation;
- verify preconditions through a trusted verifier port;
- reserve the confirmation against replay before one provider invocation;
- ignore provider claims as final proof and independently verify postconditions;
- withhold provider output on every non-verified outcome;
- require a separate recovery capability and opaque token for recoverable work;
- preserve recovery metadata after mutation-side failures without automatically
  executing undo; and
- append a terminal audit before normal lifecycle advancement.

Add strict action-audit intent and chained-record schemas. Use a private,
append-locked, `fsync`-backed JSONL SHA chain as the reference local sink.

## Consequences

All integration levels share the same authorization and release invariant.
Adapters remain replaceable, and their evidence remains useful without becoming
trusted merely because a provider emitted it. A missing request audit safely
blocks action. A missing terminal audit after possible mutation produces a
withheld recoverable failure rather than false success.

The extra verifier and durable-write operations add latency. The local chain is
tamper-evident rather than signed and the owning user can delete it. Automatic
undo remains outside this service because recovery is itself consequential and
must traverse the normal permission lifecycle.

## Alternatives rejected

- Letting each adapter enforce safety duplicates policy and creates uneven gaps.
- Treating a provider's successful return as a verified postcondition violates
  the release invariant.
- Auditing only after execution loses the required evidence when the sink is
  unavailable.
- Automatically invoking undo can compound damage without fresh authority and
  postcondition checks.
- Logging previews, outputs, raw paths, or tokens would turn the audit into a
  sensitive content store.
