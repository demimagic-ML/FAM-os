# ADR 0131: Live adaptation controls are durable and rollback to known good

**Status:** Accepted  
**Date:** 2026-07-17

## Context

ADR 0130 made live prediction advisory and verification-invariant, but an
installed owner could not see, disable, reset, evaluate, or roll it back. A
single inference result is also too weak to distinguish normal variance from a
regression. Treating every newly derived snapshot as known-good would allow a
quality, latency, thermal, or policy regression to remain active.

Prewarm and request advice have different effects. Prompt-free prewarm prepares
resident bytes under resource policy; active advice can change context or model
ordering for a request. Health gating the latter must not silently remove the
already-qualified Phase 20.6 prewarm behavior.

## Decision

The product stores one owner-scoped, revisioned, encrypted adaptation control
state in migration 0015. Active and known-good selections are explicit per
workflow. Every automatic or owner-requested transition produces an encrypted,
idempotent receipt with its before revision, resulting state, reason codes, and
exact removal counts.

A snapshot needs two terminal health samples before it can be compared. Health
is content-free and records verification quality, wall latency, observed peak
temperature when available, and policy conformance. Thermal unavailability is
explicit rather than silently healthy. A candidate is compared against the
known-good snapshot across every available dimension. Quality regression,
P95-latency regression, temperature above 85 degrees Celsius, temperature
regression above five degrees, or any policy violation causes an atomic durable
rollback and marks the candidate drifted. A healthy comparison advances the
known-good selection.

Latest verified snapshots remain eligible for resource-admitted, prompt-free
prewarm, while only the active health-controlled snapshot supplies request
context and frequency advice. Disabled adaptation and drifted snapshots cannot
start prewarm. Prewarm still has no eviction or acceptance authority.

Owner mutations require explicit confirmation:

- disable stops context, frequency, and prewarm advice but retains evidence;
- enable reconstructs eligible advice from retained verified learning;
- workflow evaluate and rollback are revisioned and receipt-bound; and
- reset atomically removes verified-learning records, snapshots, prewarm
  receipts, inference observations, health, and drift evidence while preserving
  terminal results and the control receipt ledger.

Peer-authenticated FAM Shell and authenticated, CSRF-protected FAM Console call
the same product control service. An adaptation telemetry or terminal-observer
failure is logged but cannot fail inference, change acceptance, or undo an
already committed result.

## Consequences

- The owner can inspect the complete active/known-good state and every retained
  snapshot, prewarm, health, drift, and control receipt.
- Drift decisions require repeated evidence and are reproducible from encrypted
  source sample identities.
- Disable is reversible; reset is destructive to learned behavior but not to
  completed user results or its own audit history.
- Candidate prewarm remains useful before promotion without granting candidate
  context or model-preference authority.
- The signed Phase 20.7 gate must prove restart persistence, automatic and
  manual rollback, confirmation denial, reset counts, ciphertext absence,
  diagnosis, and complete removal.
