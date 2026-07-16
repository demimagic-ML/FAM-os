# Handoff 0064: Full-workstation GPU placement and split-offload

**Date:** 2026-07-16  
**Plan step:** Phase 7.6  
**Status:** Complete  
**Previous handoff:** `0063-constrained-cpu-only-baseline.md`

## Objective

Use the reference workstation's host RAM, 22 schedulable CPU cores, RTX VRAM,
and explicit layer offload without blending memory tiers or forcing the 16 GiB
compatibility profile onto the stronger machine.

## Scope completed

- Published strict GPU placement request, decision, observed evidence, and
  full-run report roots.
- Implemented independent host-RAM and per-device-VRAM capacity decisions.
- Kept full weight plus context as a conservative host safety reservation while
  separately estimating proportional layer weights plus context in VRAM.
- Added provider-neutral exact accelerator-layer and main-device inference hints.
- Mapped those hints to Ollama API `num_gpu` and `main_gpu` options.
- Captured installed language-layer counts from live Ollama metadata.
- Executed isolated full-profile Llama and Qwen full-layer offloads.
- Executed Laguna 16/40 and Gemma 8/30 real CPU/GPU splits.
- Recorded provider residency, NVIDIA global-memory delta, cgroup peak, load
  duration, effective transfer rate, output digest, and linked observations.
- Unloaded every model and confirmed inactive service cleanup.

## Explicitly not completed

- Phase 7.7 owns SSD model storage, mmap/cache distinction, and deliberate
  cold/warm disk-I/O evidence. This run observed zero block I/O because the model
  files were already in host filesystem cache.
- Phase 7.8 owns Intel NPU feasibility and micro-experts.
- Effective transfer timing includes provider load/mapping/allocation overhead;
  it is not isolated PCIe wire time.
- Multi-GPU splitting is outside the single-RTX reference host but the contract
  already identifies one explicit device rather than using aggregate VRAM.

## Architecture and decisions

ADR 0063 rejects scalar memory, automatic unverified placement, and fictitious
host-RAM release. Admission requires both resource vectors. Exact requested
layers are verified through provider `size_vram`, while the cgroup remains the
authoritative host scope. Actual VRAM may not exceed the admitted reservation.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/gpu_contracts.py` | Vector request, decision, evidence, and run report. |
| `src/fam_os/scheduler/gpu_policy.py` | Deterministic host/VRAM admission. |
| `src/fam_os/core/ports/inference.py` | Provider-neutral exact layer/device hints. |
| `src/fam_os/adapters/ollama/payloads.py` | Ollama option mapping. |
| `configs/placement/full-workstation-gpu.json` | Four installed-model layer plan. |
| `tools/gpu_workstation/workload.py` | Sequential placement, observation, and unload. |
| `tools/run_full_gpu_placement.py` | Full-profile report runner. |
| `tests/unit/test_gpu_placement_policy.py` | Vector and fail-closed policy tests. |
| `tests/integration/test_full_gpu_placement_evidence.py` | Strict live evidence gates. |
| `docs/protocols/GPU_SPLIT_PLACEMENT.md` | Placement and transfer protocol. |
| `docs/decisions/0063-separate-host-vram-and-observe-offload.md` | Vector decision. |

## Public interfaces

- `GPU_PLACEMENT_CONTRACT_VERSION`
- `GpuPlacementRequest`, `GpuPlacementDecision`, `GpuPlacementEvidence`
- `FullWorkstationGpuReport`, `DeterministicGpuPlacementPolicy`
- `InferenceRequest.accelerator_layer_count`, `main_accelerator_index`
- `fam.scheduler.gpu-placement-{request,decision,evidence,report}/v1alpha1`
- `tools/run_full_gpu_placement.py`

## Validation

Both `/usr/bin/python3` and `/tmp/fam-os-mcp-venv/bin/python` passed 672 tests
with three expected environment-dependent skips. All 63 strict schemas and
compileall passed. The size gate checked 377 source/tool Python files with no
implementation file over 300 lines and no function over 50 lines.

The canonical report and its five integration gates passed. Observed placements:

| Model | Layers | VRAM bytes | Host compute bytes | Load seconds |
|---|---:|---:|---:|---:|
| `llama3.2:3b` | 28/28 | 2,680,611,143 | 128,941,648 | 1.596627978 |
| `qwen2.5-coder:7b` | 28/28 | 4,830,076,599 | 506,629,979 | 1.795747245 |
| `laguna-xs.2:q4_K_M` | 16/40 | 9,391,916,974 | 14,148,003,031 | 15.072812965 |
| `gemma4:26b` | 8/30 | 4,979,551,108 | 13,854,900,641 | 13.513446920 |

Every observed VRAM value remained within its conservative reservation. The
service peaked at 28,872,404,992 host bytes and 28,111,772 CPU microseconds.
`systemctl --user show fam-full-gpu.service` returned inactive/dead with
`Result=success`. Larry refreshed 1,080 files / 2,860 symbols to 19,157 nodes /
61,657 edges. The independent graph refreshed to 19,198 nodes / 61,970 edges.

## Evidence and artifacts

- `artifacts/scheduler/phase7.6/full-gpu-placement-canonical/`
- `schemas/v1alpha1/fam.scheduler.gpu-placement-request.schema.json`
- `schemas/v1alpha1/fam.scheduler.gpu-placement-decision.schema.json`
- `schemas/v1alpha1/fam.scheduler.gpu-placement-evidence.schema.json`
- `schemas/v1alpha1/fam.scheduler.gpu-placement-report.schema.json`
- `docs/decisions/0063-separate-host-vram-and-observe-offload.md`

## Known limitations and risks

- Proportional layer weight is conservative planning, not tensor-by-tensor
  allocation; provider observation remains mandatory.
- The complete context bound is reserved on both host and accelerator, which can
  under-admit but cannot manufacture free capacity.
- NVIDIA delta is device-global and can move with unrelated processes; provider
  `size_vram` owns per-model attribution.
- Gemma's context bound remains deliberately high because installed metadata does
  not expose a trustworthy KV-head count.
- Layer counts and allocation bytes are runtime/model-version specific and must
  be recaptured after upgrades.

## Operational notes

The isolated service used port 11514 and Ollama 0.30.11. It shared installed
model files but not provider process state with the user's normal Ollama service.
No model was downloaded, copied, modified, or deleted. Only models loaded by the
isolated provider were unloaded.

## Recommended next entry point

Begin Phase 7.7. Define strict artifact-storage and mmap/cache contracts; map
Ollama model manifests/blobs without recording private paths; distinguish file
size, resident pages, filesystem cache, and cgroup memory; apply explicit read
and write budgets; and capture deliberate cold-versus-warm load/eviction evidence
without representing SSD bytes as RAM. Because global cache dropping is
privileged and disruptive, prefer isolated copied/reflinked test artifacts or
`posix_fadvise(DONTNEED)` on owned descriptors with explicit effectiveness proof.
