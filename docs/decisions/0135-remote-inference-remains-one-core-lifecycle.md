# ADR 0135: Remote inference remains one Core lifecycle

**Status:** Accepted  
**Date:** 2026-07-17  
**Extends:** ADR 0134

## Context

A peer RPC can run a model without making remote execution a trustworthy product
feature. A parallel remote-task coordinator would bypass durable admission,
global attempt limits, verifier activation, terminal-result policy, learning,
and the application's normal authority surface. Treating `remote` as a model
tier also corrupts expert policy: placement and expert strength are different
facts.

## Decision

Remote inference is an optional route inside the existing durable Core inference
record. Core accepts it only when the user supplies an exact, explicitly
confirmed `RemoteExecutionAuthority`. Admission asks the trusted-peer directory
for the current enrollment, exact encrypted privacy revision, locally measured
authenticated latency, and peer-root-signed capabilities. The Fabric Scheduler
selects from those eligible declarations and persists a content-free
`RemoteExecutionPlan` before the worker starts.

Peer capability declarations bind the installed expert tier as well as device,
expert, model, capabilities, manifest digest, context ceiling, revision, and
validity. The resulting model selection retains the real economical,
specialist, escalation, or embedding tier; remote placement is represented by
the remote plan, route reason, and `remote` attempt reservation. This prevents
verified-outcome learning and escalation policy from confusing location with
expert strength.

The worker reserves one bounded remote attempt in the same durable global budget
used by repair and escalation. It derives the exact Phase 21.3 context from the
same prepared generation input used locally, rechecks privacy and capability
immediately before networking, and sends one signed request over mutual TLS. The
peer independently verifies its current signed capability, runs its installed
runtime in memory, and returns a bounded peer-signed result that binds execution,
plan, request, model, content digest, metrics, context receipt, both device
identities, and the requester's TLS certificate.

Only a complete, authenticated result becomes ordinary candidate evidence. It
then enters the existing declared verifier and terminal-result policy. A failed
verification may consume the unchanged local repair path under the same budget.
Ordinary tasks have no remote plan and open no peer connection. Remote media is
denied until a separately approved binary-context contract exists.

Shell and Console require explicit remote scope and confirmation. Neither a
paired device nor a discovered expert silently changes ordinary task routing.

## Consequences

- Remote execution cannot bypass Core admission, budgeting, verification,
  terminal retention, or verified-outcome learning.
- The peer is never trusted to report scheduling latency; the requester measures
  the authenticated round trip.
- Policy, capability, identity, receipt, or result changes fail closed before a
  candidate is released.
- Phase 21.4 proves complete request/response execution, but does not yet define
  durable complete-execution evidence or lost-response reconciliation. Those are
  Phase 21.5 and 21.6.
- The signed two-install gate is same-host evidence. Two physical Linux machines
  remain mandatory for Phase 21.7.
