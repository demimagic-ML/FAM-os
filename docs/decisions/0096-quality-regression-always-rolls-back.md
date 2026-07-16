# ADR 0096: Verification-quality regression always rolls back

- Status: accepted
- Date: 2026-07-16

## Decision

No latency or energy improvement may compensate for lower verification quality. Detected drift rolls back to the exact prior payload digest.
