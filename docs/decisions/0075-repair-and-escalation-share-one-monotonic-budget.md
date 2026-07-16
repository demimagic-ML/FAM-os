# ADR 0075: Repair and escalation share one monotonic budget

**Status:** Accepted  
**Date:** 2026-07-16

All post-failure attempts reserve worst-case tokens and wall time from one
plan-instance ledger before execution. Repair and escalation retain separate
count ceilings but share resource ceilings. Reservations are atomic, identified
by attempt and reservation, non-refundable, and cannot be reset by switching
experts. A denied reservation forbids execution.
