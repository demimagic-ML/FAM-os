# ADR 0079: Escalation reserves global budget before inference

**Status:** Accepted  
**Date:** 2026-07-16

Repair and escalation execution is decorated by the Phase 8 global ledger.
Worst-case tokens and wall time are reserved before the runtime call. Economical
initial generation is not charged to the post-failure budget. Escalation keeps
the original acceptance and exposes only bounded, digest-bound verifier context.
Budget denial raises a Core configuration failure before inference.
