# ADR 0063: Keep host RAM and VRAM separate and verify explicit layer offload

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The full workstation has 64 GiB host RAM and an RTX 5080 with roughly 16 GiB
VRAM. A scalar memory budget cannot express full or partial offload safely.
Ollama's automatic placement also cannot prove that a scheduler-requested split
was honored, and model-load duration is not pure PCIe transfer time.

## Decision

Publish strict GPU request, decision, evidence, and full-run report roots. Admit
against independent authoritative host and device capacities. Reserve complete
weights plus context on the host as a safety bound, while separately reserving a
proportional layer-weight bound plus complete context in VRAM.

Add provider-neutral exact layer-count and main-device hints to inference. Map
them to Ollama request options, then require provider-observed positive VRAM and
an observed CPU/GPU split. Account effective transfer cost with actual provider
VRAM bytes and provider load duration while explicitly disclosing that load
overhead is included.

Run all four reference inference experts sequentially in an isolated provider.
Use full layer offload for Llama/Qwen and measured partial offload for
Laguna/Gemma. Unload between placements so each reservation and transfer record
has an unambiguous owner.

## Consequences

- VRAM can no longer hide a host-memory deficit or vice versa.
- Strong models execute locally through real split-offload rather than model
  substitution or an artificial 16 GiB ceiling.
- Runtime placement is both requested and observed.
- Transfer metrics are useful and reproducible without overstating PCIe-only
  timing precision.
- Conservative host duplication may under-admit until mmap/cache calibration in
  Phase 7.7, but it cannot create unsafe fictitious capacity.
- The strict schema catalog increases from 59 to 63 roots.

## Alternatives considered

1. Let Ollama choose automatically: rejected because the requested scheduler
   decision would be unverifiable and runtime-dependent.
2. Subtract every offloaded byte from host RAM: rejected because mmap and runtime
   host retention can keep those pages charged to the cgroup.
3. Treat load duration as PCIe transfer time: rejected because provider startup,
   mapping, allocation, and initialization are included.
4. Run only models that fit fully in VRAM: rejected because it avoids the required
   Laguna/Gemma split-offload use case.

## Evidence

- `src/fam_os/scheduler/gpu_contracts.py`
- `src/fam_os/scheduler/gpu_policy.py`
- `src/fam_os/core/ports/inference.py`
- `src/fam_os/adapters/ollama/payloads.py`
- `tools/gpu_workstation/workload.py`
- `tools/run_full_gpu_placement.py`
- `tests/integration/test_full_gpu_placement_evidence.py`
- `artifacts/scheduler/phase7.6/full-gpu-placement-canonical/`
