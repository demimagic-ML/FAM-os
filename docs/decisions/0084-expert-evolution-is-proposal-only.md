# ADR 0084: Expert evolution evidence is proposal-only

- Status: accepted
- Date: 2026-07-16

## Decision

Benchmark evidence may propose splitting, merging, or retiring experts but may not mutate package lifecycle state. Deterministic minimum sample, quality-gap, redundancy, replacement-quality, and efficiency rules generate proposals. All proposals require approval and exact evidence references.

## Consequences

- Automated benchmarks cannot silently remove user capabilities.
- Small or noisy samples cause no lifecycle action.
- Retirement requires both quality and energy-efficiency dominance.
- Applying a proposal remains an auditable package-lifecycle operation.
