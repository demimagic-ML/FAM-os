# ADR 0064: Observe mmap cache and enforce model-load I/O separately from RAM

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Model manifests expose durable SSD bytes, Ollama maps weight blobs, Linux caches
mapped pages, and the service cgroup reports memory and process I/O. Treating any
one of these as the others would either invent RAM or hide cold-load cost. Global
cache dropping is privileged and disruptive, while advisory eviction of the
shared blob was not effective on this host.

## Decision

Publish strict artifact, page-cache observation, load-I/O budget, cold/warm
trial, and combined evidence contracts. Keep paths private and make the exclusion
of SSD bytes from RAM structural. Observe page residency with `mincore` and count
resident mapped pages as memory-accounted.

Use a temporary digest-verified Ollama store for deterministic cache control.
Require advisory eviction effectiveness before declaring cold. Aggregate
physical and logical I/O across the isolated service cgroup's processes, enforce
per-load cumulative byte budgets, and confirm unload after each trial.

Implement optional per-device systemd bandwidth limits and exact cgroup `io.max`
verification. Fail closed when that controller is unavailable and record the
limitation instead of claiming enforcement.

## Consequences

- SSD capacity can never increase an admission RAM budget.
- Warm cache can reduce physical reads while still consuming memory.
- Cold/warm load cost is measured on the real model format and NVMe tier.
- Cache eviction does not disrupt or mutate the user's shared model artifact.
- Hosts with delegated I/O controllers can enforce rates; this host uses the
  cumulative byte gate because `io.max` is unavailable to user services.
- The strict schema catalog increases from 63 to 66 roots.

## Alternatives considered

1. Drop global page cache: rejected as privileged and disruptive to unrelated
   applications.
2. Accept ineffective advisory eviction as cold: rejected because the claim
   would contradict `mincore` evidence.
3. Use file size as RAM usage: rejected because nonresident SSD pages consume no
   RAM while cached/mapped pages do.
4. Use cgroup `io.stat` only: rejected because the user service lacks the
   delegated I/O controller on this host; aggregate process I/O remains visible.
5. Report systemd properties as applied kernel limits: rejected because accepted
   configuration without `io.max` is not enforcement.

## Evidence

- `src/fam_os/scheduler/storage_contracts.py`
- `src/fam_os/adapters/linux/model_cache.py`
- `src/fam_os/adapters/linux/process_io.py`
- `src/fam_os/supervisor/contracts.py`
- `src/fam_os/adapters/systemd/commands.py`
- `src/fam_os/adapters/cgroup/parsing.py`
- `src/fam_os/supervisor/limit_verification.py`
- `tools/storage_paging/owned_store.py`
- `tools/storage_paging/workload.py`
- `tests/integration/test_storage_paging_evidence.py`
- `artifacts/scheduler/phase7.7/llama-storage-paging-canonical/`
