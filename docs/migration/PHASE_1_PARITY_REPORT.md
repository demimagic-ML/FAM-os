# Phase 1 measured parity report

**Date:** 2026-07-16  
**Hardware:** Intel Core Ultra 9 285K host, 64 GiB physical RAM, 2 TB SSD, optional RTX 5080 present  
**Reference constraint:** CPU-only user service, 16 GiB `MemoryMax`, zero `MemorySwapMax`, 2K expert context unless noted

## Outcome

Phase 1.10 passed. FAM_OS reproduced the parent prototype's tests, 24-case routing benchmark, constrained expert activation, fresh-service residency comparison, and verified 7B-to-14B escalation without importing parent implementation modules into `FAM_OS/src`.

Canonical machine report: `artifacts/parity/phase1-parity-20260716-095056-252893.json`.

## Test parity

- 103 FAM_OS tests passed.
- 10 parent RNF tests passed unchanged.
- Linux hardware profile parity passed.
- Live Ollama lifecycle and metrics passed.
- Live user-systemd/cgroup lifecycle passed.
- Three live Bubblewrap isolation, timeout, and output-bound tests passed.
- Two parent-versus-FAM Python verifier parity tests passed.

## Routing parity

| Metric | Parent reference | FAM_OS |
|---|---:|---:|
| Accuracy | 23/24 (95.8%) | 23/24 (95.8%) |
| Valid JSON | 23/24 (95.8%) | 23/24 (95.8%) |
| Mean wall time | 2.015 s | 2.103 s |
| Throughput | 24.18 tok/s | 22.98 tok/s |
| Peak service memory | 2.30 GB | 2.30 GB |

Both runs missed `kernel-03`; all code, math, and retrieval cases passed. FAM_OS used the migrated `ModelTaskRouter`, routing evaluation policy, and Ollama adapter.

## Residency policy parity

| Policy | Peak memory | Expert wall | Load | Throughput |
|---|---:|---:|---:|---:|
| Persistent Granite + 14B | 12.19 GiB | 74.65 s | 6.91 s | 4.66 tok/s |
| Confirmed Granite eviction + 14B | 11.30 GiB | 76.62 s | 7.92 s | 4.59 tok/s |
| Persistent Granite + 7B | 6.24 GiB | 34.47 s | 3.39 s | 9.03 tok/s |

All services stayed below 16 GiB, used zero swap and zero accelerator memory, and recorded zero OOM kills. The 7B operational preference reproduced. Confirmed router eviction reduced the current 14B peak by about 0.90 GiB.

The first migrated comparison exposed an unload race: the runtime acknowledged eviction while `/api/ps` still listed Granite, and overlapping activation erased the expected memory benefit. That failed report is preserved at `artifacts/parity/policy-parity-20260716-093229-742050.json`. ADR 0009 changes `InferenceRuntime.unload` to require confirmed absence.

## Verified escalation parity

| Attempt | Model | Wall | Load | Verification |
|---|---|---:|---:|---|
| Economical | `qwen2.5-coder:7b` | recorded in artifact | recorded in artifact | Failed |
| Repair | `qwen2.5-coder:7b` | recorded in artifact | recorded in artifact | Failed |
| Escalation | `qwen2.5-coder:14b` | recorded in artifact | recorded in artifact | Passed in Bubblewrap |

The final status was `verified_after_escalation`. The result contained only the passing 14B candidate. Peak service memory was 11.46 GiB, swap remained zero, accelerator memory was zero, and no OOM kill occurred.

## Canonical artifacts

- `artifacts/parity/routing-parity-20260716-094554-188044.json`
- `artifacts/parity/policy-parity-20260716-094449-098883.json`
- `artifacts/parity/verified-parity-20260716-094942-805211.json`
- `artifacts/parity/phase1-parity-20260716-095056-252893.json`

The reports contain trusted local benchmark prompts and generated candidates. They are migration evidence, not user-facing API responses or production telemetry schemas.
