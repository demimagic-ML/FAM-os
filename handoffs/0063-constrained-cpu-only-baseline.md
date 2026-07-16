# Handoff 0063: Constrained CPU-only 16 GiB baseline

**Date:** 2026-07-16  
**Plan step:** Phase 7.5  
**Status:** Complete  
**Previous handoff:** `0062-deterministic-admission-and-eviction.md`

## Objective

Prove a real multi-expert workload remains inside an exact 16 GiB CPU-only
service ceiling on the stronger reference host, without falsifying host capacity
or substituting weaker models for unsafe requests.

## Scope completed

- Published a strict CPU-baseline report with resource, execution, rejection,
  simultaneous-residency, cleanup, and observation-chain invariants.
- Corrected executable composition to constrain scheduler commitment inside the
  service envelope rather than requiring a large host to report only 16 GiB.
- Applied the effective 23-core scheduler CPU quota when no narrower
  service-specific quota is declared.
- Started a separate 16 GiB/zero-swap CPU-only Ollama service.
- Admitted and executed Llama 3.2 3B, then Qwen 2.5 Coder 7B while Llama remained
  loaded; both provider records reported exactly zero accelerator bytes.
- Evaluated and rejected Laguna XS.2 and Gemma 4 26B before provider mutation.
- Evicted both admitted experts through the durable coordinator and confirmed an
  empty provider plus inactive service cleanup.
- Captured seven linked authoritative cgroup observations and strict evidence.

## Explicitly not completed

- Phase 7.6 owns RTX placement, RAM/VRAM split-offload, and transfer cost.
- Phase 7.7 owns SSD mmap/cache and disk-I/O budgeting.
- The strong-model quality smoke rerun is not a compatibility-profile task;
  Laguna and Gemma remain required full-profile candidates.
- This baseline does not claim the user's ordinary Ollama service is CPU-only;
  only the isolated `fam-cpu-baseline` cgroup is evidence.

## Architecture and decisions

ADR 0062 keeps host discovery truthful while applying the compatibility ceiling
to the service cgroup. Admission consumes the cgroup-clamped live view. The
strict report makes simultaneous residency, zero VRAM/swap/OOM, strong-model
rejection, and inactive cleanup structural rather than narrative claims.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/baseline_contracts.py` | Strict CPU baseline report and attempt invariants. |
| `tools/parity/composition.py` | Scheduler-plus-reserve service-envelope gate. |
| `tools/parity/profile_service.py` | Effective CPU quota enforcement. |
| `tools/cpu_baseline/workload.py` | Live admission, inference, observation, and eviction sequence. |
| `tools/run_cpu_only_baseline.py` | Canonical runner and report serialization. |
| `tests/integration/test_cpu_only_baseline_evidence.py` | Strict live evidence gate. |
| `docs/protocols/CPU_ONLY_16GIB_BASELINE.md` | Baseline protocol. |
| `docs/decisions/0062-constrain-service-not-host-for-compatibility.md` | Envelope decision. |

## Public interfaces

- `CPU_BASELINE_CONTRACT_VERSION`, `CPU_ONLY_ENVIRONMENT`
- `CpuBaselineExpertAttempt`, `CpuOnlyBaselineReport`
- `fam.scheduler.cpu-baseline/v1alpha1`
- `tools/run_cpu_only_baseline.py`

## Validation

Both `/usr/bin/python3` and `/tmp/fam-os-mcp-venv/bin/python` passed 659 tests
with three expected environment-dependent skips. All 59 strict schemas and
compileall passed. The final size gate checked 373 source/tool Python files with
no implementation file over 300 lines and no function over 50 lines.

The canonical strict report decoded and its five integration gates passed. It
records 6,981,943,296 peak bytes under 17,179,869,184, a 2,147,483,648-byte
reserve, zero swap, zero OOM kills, 12,320,787 CPU microseconds, seven linked
authoritative observations, and 23 schedulable CPU cores. Llama and Qwen were
simultaneously resident at 2,146,812,557 and 4,853,375,958 provider bytes with
zero VRAM. Laguna and Gemma have explicit insufficient-safe-memory decisions.

`systemctl --user show fam-cpu-baseline.service` returned `inactive/dead` with
`Result=success`. Larry refreshed 1,060 files / 2,834 symbols to 18,162 nodes /
59,765 edges. The independent graph refreshed to 18,203 nodes / 60,147 edges.

## Evidence and artifacts

- `artifacts/scheduler/phase7.5/cpu-only-multi-expert-canonical/`
- `artifacts/scheduler/phase7.5/cpu-only-multi-expert-diagnostic/` (first valid
  run before simultaneous-residency became a strict report field)
- `schemas/v1alpha1/fam.scheduler.cpu-baseline.schema.json`
- `docs/decisions/0062-constrain-service-not-host-for-compatibility.md`

## Known limitations and risks

- Provider resident bytes reflect Ollama's model accounting, while cgroup peak
  remains the authoritative total process-scope ceiling.
- The main Ollama service had an unrelated Nomic GPU process during the final
  cleanup check; it is outside the isolated service, was not mutated, and is not
  used as baseline evidence.
- CPU compatibility proves safety and lifecycle behavior, not acceptable latency
  for 26B/33B experts.
- A future model/runtime version may change resident bytes and requires a fresh
  canonical capture rather than reusing these numbers.

## Operational notes

The isolated service used port 11513 and the shared read-only installed model
store. No model was downloaded, copied, modified, or deleted. The runner unloaded
only the two models it loaded in its isolated provider and did not stop or unload
the user's ordinary Ollama service.

## Recommended next entry point

Begin Phase 7.6. Define a vector placement contract that separates host RAM from
per-device VRAM, records weight and context partitioning, proves layer/split
allocation against Ollama's actual `size`/`size_vram`, accounts host-to-device
transfer bytes and time, and runs full-profile Llama/Qwen plus Laguna and Gemma
where admitted. Preserve the Phase 7.5 CPU baseline as an independent regression,
not as the default mode for this workstation.
