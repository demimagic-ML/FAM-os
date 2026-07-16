# Handoff 0068: Bounded predictive prefetch

**Date:** 2026-07-16  
**Plan step:** Phase 7.10  
**Status:** Complete  
**Previous handoff:** `0067-cache-telemetry-policy-replay.md`

## Objective

Reduce likely next-model storage latency without allowing speculation to bypass
admission, consume unbounded I/O, erode the operating-system reserve, evict
resident work, or hide false-positive cost.

## Scope completed

- Added digest-bound historical access sequences and declared prefetch candidates.
- Implemented a deterministic immediate-transition predictor with minimum two
  observations, confidence threshold, stable tie-breaking, horizon, and expiry.
- Added independent byte, read-I/O, tier-capacity, host-reserve, concurrency, and
  speculative-waste budgets.
- Implemented fail-closed admission with explicit reasons and zero eviction authority.
- Added an owned-root exact-range Linux prefetch adapter using bounded `pread`.
- Derived two real Llama-to-Qwen transitions from Phase 7.5 and 7.6 evidence.
- Cloned the installed Qwen artifact into a temporary digest-verified store,
  evicted its private cache, prefetched exactly 32 MiB, and repeated the range as
  demand.
- Captured cache before/after, logical and physical I/O, equal content digests,
  prediction/admission linkage, timely use, and clone cleanup.
- Proved a counterfactual second speculation is rejected at the waste ceiling.
- Added five strict schema roots, tests, protocol documentation, ADR 0067,
  Master Plan closure, canonical artifacts, and this handoff.

## Explicitly not completed

- Prefetch does not activate an expert or reserve inference context.
- Prefetch cannot unload or evict any artifact.
- The transition predictor is intentionally bounded and does not claim general
  workload prediction or learned intelligence.
- The waste-guard request proves prospective enforcement; it does not mislabel
  the successful live prefetch as wasted.
- Production aggregation of long-term prediction outcomes remains future
  operational telemetry, not a hidden claim in this phase.

## Architecture and decisions

ADR 0067 separates prediction, resource admission, and file execution. Repeated
history is necessary but insufficient: an otherwise valid prediction is still
rejected if any resource, expiry, concurrency, reserve, or waste gate fails.
Admission decisions cannot contain evictions.

The execution adapter is limited to an exact byte range beneath an owned root.
It measures process physical reads around each operation and hashes all bytes.
The canonical workload clones the real artifact so cache manipulation cannot
evict pages belonging to the installed shared Ollama store.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/prefetch_prediction.py` | History, candidates, requests, predictions. |
| `src/fam_os/scheduler/prefetch_predictor.py` | Deterministic transition predictor. |
| `src/fam_os/scheduler/prefetch_contracts.py` | Budgets, admission, execution, report. |
| `src/fam_os/scheduler/prefetch_policy.py` | Fail-closed prefetch resource policy. |
| `src/fam_os/adapters/linux/bounded_prefetch.py` | Exact-range read and physical-I/O evidence. |
| `tools/run_predictive_prefetch.py` | Historical composition and live owned-clone run. |
| `tests/unit/test_predictive_prefetch.py` | Prediction and every admission bound. |
| `tests/integration/test_predictive_prefetch_evidence.py` | Canonical live evidence gates. |
| `docs/protocols/BOUNDED_PREDICTIVE_PREFETCH.md` | Prediction/admission/execution protocol. |
| `docs/decisions/0067-prefetch-only-with-history-and-hard-bounds.md` | Prefetch decision. |
| `artifacts/scheduler/phase7.10/qwen-predictive-prefetch-canonical/` | Strict report and summary. |

## Public interfaces

- `PREFETCH_CONTRACT_VERSION`, `PREFETCH_PREDICTOR_VERSION`, `PREFETCH_POLICY_VERSION`
- `ArtifactAccessSequence`, `PrefetchCandidate`, `PrefetchPredictionRequest`
- `PrefetchPrediction`, `DeterministicTransitionPredictor`
- `PrefetchResourceBudget`, `PrefetchPolicyRequest`, `PrefetchPolicyDecision`
- `PrefetchExecutionEvidence`, `PredictivePrefetchReport`
- `DeterministicPrefetchAdmissionPolicy`, `BoundedFilePrefetcher`
- five `fam.scheduler.prefetch-*` / `predictive-prefetch-report` schema roots

## Canonical live evidence

Directory: `artifacts/scheduler/phase7.10/qwen-predictive-prefetch-canonical/`

- Supporting transitions: two, from digest-bound CPU baseline and GPU placement.
- Confidence: 1.0; minimum observations: two.
- Candidate: installed Qwen model blob, private cloned copy for execution.
- Prefetch reservation: 33,554,432 bytes.
- OS reserve: 12,884,901,888 bytes.
- Concurrency ceiling: one.
- Cache before/after: 0 / 33,685,504 bytes.
- Prefetch logical/physical reads: 33,554,432 / 33,685,504 bytes.
- Demand logical/physical reads: 33,554,432 / 0 bytes.
- Prefetch and demand SHA-256 digests match.
- Waste guard: rejected with `budget.maximum_waste_exceeded`.
- Temporary Qwen store: removed.

## Validation

Both supported Python environments passed 715 tests with three expected skips.
All 76 generated schemas and compileall passed. The size audit checked 399
source/tool Python files with no file above 300 lines and no function above 50.

Larry refreshed 1,193 files, 2,993 symbols, 21,560 graph nodes, and 66,921 edges.
This handoff itself is the one expected map-stale file.

## Phase 7 exit gate

Phase 7 is now complete. The retained evidence jointly proves the real 16 GiB
CPU ceiling and reserve, full workstation CPU/RAM/RTX/NVMe use, context estimates,
durable residency, deterministic admission/eviction, split GPU placement,
SSD/page-cache accounting, Intel NPU feasibility, tier-separated replay, and
bounded prefetch. Decisions preserve separate resource domains and explain
placement, transfer, cache, eviction, and speculation without weakening either
validation profile.

## Known limitations and risks

- `/proc/self/io` physical counters are Linux-process evidence and depend on the
  kernel/filesystem implementation.
- Exact-range reads may cause bounded kernel read-ahead, so physical reads can
  slightly exceed logical prefetch bytes; admission reserves logical requested
  bytes and evidence records the observed physical amount.
- Learned or multi-step prediction requires a new policy version and benchmark.

## Recommended next entry point

Begin Phase 8.1 by auditing the current verifier manifest and trust model against
the Phase 8 exit gate. Preserve the existing Python verifier evidence, identify
which verifier kinds and trust/attestation fields remain absent, and implement
the first missing contract rather than rewriting the proven code path.
