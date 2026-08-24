# Handoff 0134: Profile-derived worker cgroups

**Date:** 2026-07-17  
**Plan step:** Phase 17.6  
**Status:** Complete  
**Previous handoff:** `0133-managed-ollama-runtime.md`

## Scope completed

- Versioned model, verifier, connector, and training worker shares.
- Derived MemoryHigh, MemoryMax, swap, CPU, and task ceilings.
- Systemd adapter applies MemoryHigh in addition to existing limits.
- Current workstation live service observed every requested cgroup ceiling.
- VRAM remains a Scheduler placement budget rather than a false systemd limit.

## Validation

Focused contracts, schema round-trips, lint, typing, and live systemd property
inspection pass. The schema catalog contains 180 artifacts.

## Recommended next entry point

Phase 17.7: build a signed complete release artifact containing the wheel,
schemas, Console assets, migrations, units, and connectors; install only from
that artifact and prove update/rollback/remove.
