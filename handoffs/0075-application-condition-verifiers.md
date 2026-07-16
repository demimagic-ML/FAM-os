# Handoff 0075: Application condition verifiers

**Date:** 2026-07-16  
**Plan step:** Phase 8.7  
**Status:** Complete  
**Previous handoff:** `0074-retrieval-citation-verifier.md`

Bound application condition providers to exact allowed verifier activation.
Retained the proven Core behavior: preconditions run before mutation,
postconditions after provider execution, output is released only on all-pass,
malformed/provider-only evidence is rejected, audit is mandatory, and recovery
metadata survives unverified mutation. Added activation mismatch tests and reran
the full action safety integration path. See protocol and ADR 0074.

Next implement Phase 8.8 as one global budget ledger shared by initial attempts,
repair, and escalation, with monotonic time/token charging and fail-closed
reservation/settlement.
