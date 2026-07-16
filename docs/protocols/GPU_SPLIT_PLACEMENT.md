# Full-workstation GPU split placement

Phase 7.6 treats host RAM and each accelerator's VRAM as separate resource
vectors. Neither one can satisfy a deficit in the other.

## Planning model

A request binds a linked live observation, a context-free weight bound, a
weight-free context bound, the installed model's language-layer count, an exact
requested offload layer count, and one accelerator device.

The current conservative planner computes:

- accelerator weight bytes as the ceiling of
  `weight_bound * requested_layers / model_layers`;
- accelerator context as the complete context bound;
- accelerator reservation as those two values added together;
- host compute weight as the remaining proportional weight;
- host safety reservation as the complete weight plus complete context.

The host safety reservation intentionally does not subtract offloaded weights.
Ollama may mmap or retain host-side pages even for GPU layers, so only the live
cgroup is authoritative for actual host usage. This conservative duplication is
explicit and prevents VRAM from being misrepresented as RAM relief.

Admission requires both vectors to fit the newest authoritative observation.
Degraded host telemetry, missing VRAM telemetry, disabled placement, or either
capacity shortfall rejects before provider mutation.

## Execution and verification

`InferenceRequest.accelerator_layer_count` and `main_accelerator_index` are
provider-neutral placement hints. The Ollama adapter maps them to API `num_gpu`
and `main_gpu`. The provider's loaded-model record must then report positive
`size_vram`; FAM records total provider residency, accelerator residency, and the
derived host compute portion. Observed VRAM may not exceed the admitted bound.

Transfer cost uses actual provider accelerator bytes divided by Ollama's model
load duration. The contract explicitly marks that duration as including provider
load overhead; it is an effective load/offload cost, not a claim of isolated PCIe
wire time. NVIDIA global-memory delta is retained independently as corroboration.

## Canonical workstation result

The isolated full-profile run at
`artifacts/scheduler/phase7.6/full-gpu-placement-canonical/` records:

| Model | GPU layers | Provider VRAM | Provider host compute | Load time |
|---|---:|---:|---:|---:|
| Llama 3.2 3B | 28/28 | 2,680,611,143 | 128,941,648 | 1.597 s |
| Qwen 2.5 Coder 7B | 28/28 | 4,830,076,599 | 506,629,979 | 1.796 s |
| Laguna XS.2 | 16/40 | 9,391,916,974 | 14,148,003,031 | 15.073 s |
| Gemma 4 26B | 8/30 | 4,979,551,108 | 13,854,900,641 | 13.513 s |

The service used 22 schedulable CPU cores, peaked at 28,872,404,992 host bytes,
executed both strong models with real CPU/GPU splits, unloaded every model, and
finished inactive. The user's ordinary Ollama service remained outside the
isolated service boundary.
