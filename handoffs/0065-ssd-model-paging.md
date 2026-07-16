# Handoff 0065: SSD model paging, mmap cache, and I/O budgets

**Date:** 2026-07-16  
**Plan step:** Phase 7.7  
**Status:** Complete  
**Previous handoff:** `0064-full-workstation-gpu-placement.md`

## Objective

Use the NVMe model tier without representing SSD as RAM, and make artifact
identity, mmap cache residency, cold/warm load cost, eviction, and disk-I/O
budgets explicit and verifiable.

## Scope completed

- Published strict SSD artifact, page-cache observation, load-I/O budget,
  cold/warm trial, and combined evidence roots.
- Resolved Ollama model blobs from manifests with size, regular-file, symlink,
  root-containment, digest, and path-privacy boundaries.
- Implemented Linux `mincore` page-residency observation without faulting the
  model into memory.
- Implemented read-only no-follow `POSIX_FADV_DONTNEED` cache advice.
- Refused to label the shared blob cold when advice was ineffective.
- Created a temporary private digest-verified Ollama store for deterministic
  cache control without mutating the user's model store.
- Aggregated physical and logical `/proc` I/O across isolated-service processes.
- Enforced per-load cumulative physical read and write byte budgets.
- Added optional per-device block-I/O bandwidth limits to service definitions,
  systemd projection, cgroup `io.max` observation, and exact fail-closed applied
  limit verification.
- Captured real cold/warm CPU loads of the 2.019 GB Llama artifact and confirmed
  unload plus inactive cleanup.

## Explicitly not completed

- Phase 7.8 owns Intel NPU investigation.
- Phase 7.9 owns multi-run cache telemetry policy replay.
- Phase 7.10 owns predictive prefetch.
- The workstation user manager does not delegate `io.max`; kernel rate limits
  are implemented but unavailable in canonical evidence. Cumulative process-I/O
  budgets are active and the missing controller is explicit.
- The temporary cloned store is test isolation, not a second permanent model
  registry; production packages continue referencing the user-owned artifact.

## Architecture and decisions

ADR 0064 separates durable artifact bytes, resident cache pages, cgroup memory,
logical reads, and physical reads. SSD bytes are structurally excluded from RAM.
Cold requires observed eviction effectiveness. Optional rate enforcement must be
read back from `io.max`; accepted systemd properties alone are insufficient.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/storage_contracts.py` | Storage/cache/budget/trial/evidence invariants. |
| `src/fam_os/adapters/linux/model_cache.py` | Private blob resolver, mincore, and safe cache advice. |
| `src/fam_os/adapters/linux/process_io.py` | Aggregate service-cgroup process I/O. |
| `src/fam_os/supervisor/contracts.py` | Provider-neutral block-I/O bandwidth limits and ceilings. |
| `src/fam_os/adapters/systemd/commands.py` | Systemd read/write bandwidth properties. |
| `src/fam_os/adapters/cgroup/parsing.py` | `io.max` parsing. |
| `src/fam_os/adapters/cgroup/observer.py` | Applied `io.max` observation. |
| `src/fam_os/supervisor/limit_verification.py` | Exact dynamic per-device verification. |
| `tools/storage_paging/owned_store.py` | Temporary byte/digest-verified Ollama store. |
| `tools/storage_paging/workload.py` | Cold/warm load and budget sequence. |
| `tools/run_storage_paging.py` | Canonical evidence runner. |
| `tests/integration/test_storage_paging_evidence.py` | Strict live evidence gates. |
| `docs/protocols/SSD_MODEL_PAGING.md` | Paging and I/O protocol. |
| `docs/decisions/0064-observe-mmap-cache-and-enforce-io-separately.md` | Tier decision. |

## Public interfaces

- `STORAGE_PAGING_CONTRACT_VERSION`
- `ModelStorageArtifact`, `ArtifactCacheObservation`
- `ModelLoadIoBudget`, `ModelLoadIoTrial`, `StoragePagingEvidence`
- `BlockIoBandwidthLimit`, `BlockIoBandwidthCeiling`
- `fam.scheduler.storage-artifact/v1alpha1`
- `fam.scheduler.artifact-cache/v1alpha1`
- `fam.scheduler.storage-paging-evidence/v1alpha1`
- `tools/run_storage_paging.py`

## Validation

Both `/usr/bin/python3` and `/tmp/fam-os-mcp-venv/bin/python` passed 684 tests
with three expected environment-dependent skips. All 66 strict schemas and
compileall passed. The size gate checked 383 source/tool Python files with no
implementation file over 300 lines and no function over 50 lines.

The canonical report and five live integration gates passed:

- artifact: 2,019,377,376 bytes, NVMe/ext4, path private;
- pre-eviction cache: 2,019,377,376 bytes;
- cold pre-load cache: 0 bytes;
- cold physical/logical reads: 2,019,602,432 / 2,099,023,919 bytes;
- cold load: 3.237755975 seconds;
- warm pre-load cache: 2,019,377,376 bytes;
- warm physical/logical reads: 0 / 2,098,744,241 bytes;
- warm load: 1.928527196 seconds;
- both trials: confirmed unload, zero write-budget breach;
- service: inactive/dead, result success; temporary store removed.

Larry refreshed 1,097 files / 2,897 symbols to 19,471 nodes / 62,783 edges. The
independent graph refreshed to 19,515 nodes / 63,124 edges.

## Evidence and artifacts

- `artifacts/scheduler/phase7.7/llama-storage-paging-canonical/`
- `schemas/v1alpha1/fam.scheduler.storage-artifact.schema.json`
- `schemas/v1alpha1/fam.scheduler.artifact-cache.schema.json`
- `schemas/v1alpha1/fam.scheduler.storage-paging-evidence.schema.json`
- `docs/decisions/0064-observe-mmap-cache-and-enforce-io-separately.md`

## Known limitations and risks

- `mincore` is a point-in-time view; unrelated memory pressure can evict pages
  immediately afterward.
- Per-process physical counters can miss a child that exits before observation;
  the provider remains loaded during sampling in the canonical workflow.
- Shared-blob advice was ineffective on this kernel/filesystem state. Production
  must observe the result and cannot assume advice succeeded.
- Temporary store cloning adds setup I/O outside the measured service. Only the
  isolated provider trial is included in cold/warm counters.
- Kernel bandwidth support is host/delegation dependent; unavailable observation
  fails constrained startup rather than degrading silently.

## Operational notes

The canonical service used port 11515 with CPU placement (`num_gpu=0`). The
private store was under a random temporary directory and removed after service
cleanup. No user model, manifest, or blob was changed or deleted. The rejected
shared-cache diagnostic produced no accepted artifact.

## Recommended next entry point

Begin Phase 7.8. Inspect the actual Intel NPU PCI/driver/runtime state, distinguish
hardware presence from usable inference runtime, inventory installed OpenVINO or
Level Zero capabilities, define micro-expert compatibility requirements, and run
a bounded real inference only if the detected NPU stack supports it. Record an
honest unsupported result if hardware or runtime is absent; do not emulate NPU on
CPU and call that NPU evidence.
