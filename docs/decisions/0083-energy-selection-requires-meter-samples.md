# ADR 0083: Quality-per-joule requires raw meter samples

- Status: accepted
- Date: 2026-07-16

## Decision

FAM calculates quality-per-joule only when a hardware meter supplies at least two timestamped power samples during the benchmark interval. Joules are integrated from those samples. No TDP, utilization percentage, model size, or generic device estimate may substitute for observed energy.

Quality-per-byte, quality-per-second, and quality-per-joule retain separate winners and the complete underlying measurements.

## Consequences

- Reports are auditable and hardware-specific.
- Machines without an energy meter cannot claim quality-per-joule.
- Residency and cold-load state affect measurements and must be interpreted with benchmark context.
- Selection policy can optimize an explicit dimension without hiding tradeoffs in one composite score.
