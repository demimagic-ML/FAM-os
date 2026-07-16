# ADR 0038: Release only registry-backed terminal evidence

**Status:** Accepted  
**Date:** 2026-07-16

## Decision

Build `TaskResult` only from terminal snapshots. Resolve candidate content from a
trusted evidence registry; never accept content as an assembly argument. For
verified plans require passing acceptance evidence linked to the exact candidate
and release predecessor requirements. Map every non-release or blocking
degradation to content-free safe results.

## Consequences

- Failed candidate content cannot cross the release boundary.
- Verification IDs alone are insufficient without linked passing evidence.
- A release terminal is necessary but not sufficient for release.
- Evidence storage remains replaceable behind a port.

## Evidence

- `src/fam_os/core/lifecycle/final_service.py`
- `tests/unit/test_core_final_result_policy.py`
- `docs/protocols/CORE_FINAL_RESULT_POLICY.md`
