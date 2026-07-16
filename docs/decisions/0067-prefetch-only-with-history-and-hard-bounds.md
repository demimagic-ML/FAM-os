# ADR 0067: Prefetch only with repeated history and hard resource bounds

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Predictive model loading can reduce latency, but a wrong prediction consumes
memory and disk bandwidth before any user demand exists. An unconstrained
predictor could evict active experts, erode the OS reserve, or amplify SSD I/O.

## Decision

FAM separates prediction, admission, and execution. The deterministic v1
predictor requires at least two supporting immediate transitions and a declared
confidence threshold. Admission independently enforces cache bytes, read I/O,
tier capacity, host reserve, concurrency, expiry, and speculative-waste limits.
Prefetch has no eviction authority.

Execution is exact-range and restricted to an owned artifact root. Evidence
must bind prediction history by digest, retain the admitted decision, measure
page-cache change and physical I/O, compare prefetch/demand digests, and prove
temporary-artifact cleanup.

## Consequences

- A prediction can be valid but still rejected by resource policy.
- Insufficient history results in no action rather than a weaker heuristic.
- Prefetch cannot displace active or protected work.
- The first implementation warms bounded SSD-backed pages; expert activation
  remains under ordinary admission and residency policy.
- The waste guard is enforceable before another speculation. Durable production
  outcome aggregation can be added only with a versioned contract.
