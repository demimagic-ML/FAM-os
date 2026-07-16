# Constrained CPU-only 16 GiB baseline

Phase 7.5 is the minimum-machine execution proof. It is intentionally separate
from the full-workstation GPU proof in Phase 7.6.

## Fixed envelope

The isolated Ollama service receives an exact 16 GiB `MemoryMax`, zero
`MemorySwapMax`, and the effective profile's schedulable CPU quota. The scheduler
may commit at most 14 GiB, preserving 2 GiB inside the service envelope as an
operating-system/runtime reserve. CUDA, Vulkan, and Ollama GPU runtime selection
are denied through the four exact environment settings carried by the strict
report.

The host may have more than 16 GiB. The executable composition therefore checks
`scheduler_limit + reserve <= service envelope`; it does not incorrectly require
the host's physical/effective capacity to shrink to the service ceiling. The
live sampler then clamps decisions to the actual service cgroup.

## Workload

The canonical run:

1. starts an isolated service and takes an authoritative baseline observation;
2. admits and executes Llama 3.2 3B on CPU;
3. admits and executes Qwen 2.5 Coder 7B while Llama remains resident;
4. proves both models are simultaneously resident and each reports zero VRAM;
5. evaluates Laguna XS.2 and Gemma 4 26B against the same live scope and records
   explicit insufficient-memory rejections without loading or substituting them;
6. evicts Qwen and Llama through durable persist-before-unload coordination;
7. confirms no loaded models remain and stops the isolated service.

Every stage extends the linked cgroup observation chain. The strict report also
requires zero swap use, zero OOM kills, peak memory below the exact ceiling,
positive CPU use, two executed experts, the two named strong-model rejections,
and inactive cleanup.

## Canonical result

`artifacts/scheduler/phase7.5/cpu-only-multi-expert-canonical/` records seven
linked observations, 23 schedulable CPU cores, 6,981,943,296 peak service bytes,
12,320,787 CPU microseconds, zero swap, zero OOM kills, and zero accelerator
bytes for both executed models. The user's ordinary Ollama service is outside
this cgroup and is neither stopped nor used as evidence for the baseline.
