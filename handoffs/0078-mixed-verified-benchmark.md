# Handoff 0078: Mixed verified benchmark

**Date:** 2026-07-16  
**Plan step:** Phase 9.1  
**Status:** Complete  
**Previous handoff:** `0077-sandbox-process-limit-correction.md`

## Completed

- Added strict suite, case, strong-run reference, and report contracts/schemas.
- Required kernel-only, code, math, retrieval, and application coverage.
- Bound every fixture and raw strong-model report by SHA-256.
- Retained stable-topological-sort v2 as a named regression.
- Ran packaged Laguna and Gemma independently on the full workstation.
- Laguna passed after one policy-bounded repair with trusted tests/examples.
- Gemma passed its initial candidate.
- Executed the mixed suite; every case passed its exact acceptance policy.
- Added positive, omission, model-duplication, and kernel-no-model tests.

## Important history

The first two strong runs were correctly withheld because handoff 0070's
real-user-wide `RLIMIT_NPROC` prevented Bubblewrap startup. Handoff 0077 and ADR
0076 corrected that implementation with a delegated `TasksMax` scope. The raw
failed files remain historical; the mixed report references only the subsequent
live-isolated successful runs.

## Next entry point

Implement Phase 9.2 micro-experts as deterministic, versioned, locally packaged
classifiers for routing, language, safety, and complexity. Benchmark them against
explicit labels and ensure a micro-expert can advise routing but never grant
permission or bypass acceptance.
