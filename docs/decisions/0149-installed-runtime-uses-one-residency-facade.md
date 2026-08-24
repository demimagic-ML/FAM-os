# ADR 0149: Installed model operations use one residency facade

Status: Accepted

## Context

Phase 7 had durable cold, warm, active, and evicting contracts, deterministic
warm-only eviction, exact context estimation, and confirmed Ollama unloads.
The installed task worker did not use them. Predictive prewarming, document
embeddings, remote execution, synthetic teachers, and factory canaries also
received the raw runtime independently. Explicit eviction could therefore not
be enabled without risking an in-flight model call.

Startup had a second protocol mismatch: a missing state file was initialized as
all-cold before the first provider observation. Although immediate reconciliation
usually corrected it, the first durable state had not proved provider absence.

## Decision

The product composes one `ProductionModelResidency` around the raw Ollama
runtime. Catalog chat and embedding calls perform live resource admission,
execute stable warm-only evictions through the persist-before-unload barrier,
load the selected model, acquire a durable process lease, hold one reentrant
critical section for the complete provider call, and release the lease in a
`finally` path.

Generation uses the observed autoregressive KV profile. Embedding uses an
encoder-activation profile with a conservative UTF-8-byte token upper bound and
the request batch size as concurrent sequences. Requests that do not leave room
for reserved output or exceed observed model context fail before inference.

All auxiliary production consumers receive the same facade. Temporary factory
canary models remain outside the signed catalog and eviction set, but their
provider calls are serialized. Predictive prewarming keeps its separate
no-eviction resource policy. The task worker retains its real Core request ID in
the lease while other consumers receive unique operation IDs.

Managed Ollama is the only mode that grants FAM eviction authority. External
Ollama can be observed and leased, but a memory shortfall is rejected rather
than unloading user-owned models. Reclaimable selection capacity includes only
provider-confirmed warm catalog records.

The initial durable catalog is built directly from one provider snapshot. On
restart, process-owned leases are durably recovered before reconciliation,
because their worker threads cannot survive the process boundary.

## Consequences

- No FAM-initiated unload can overlap local inference or embedding.
- Active and temporary models are never deterministic eviction candidates.
- A failed provider call still releases its lease; an ambiguous unload retains
  the existing evicting recovery semantics.
- Product startup fails closed when provider residency cannot be observed.
- Local provider operations are serialized. This trades throughput for a
  provable eviction boundary until measured concurrent placement is designed.
- Injected test runtimes must implement observable prewarm/unload semantics and
  provide a context-profile observer; production metadata is never fabricated.
- This closes source composition only. A fresh signed installed matrix and the
  Phase 23 soak are still required.

## Alternatives considered

- Wiring the legacy `PlacementExecutor` was rejected because it unloads models
  without active leases or durable confirmed-eviction coordination.
- Protecting only the main task worker was rejected because embedding,
  prewarming, remote, and factory paths share the same provider.
- Assuming every model is cold at startup was rejected because persisted state
  must follow provider evidence, not initialization convenience.
- Allowing external Ollama eviction was rejected because FAM does not own that
  service or its unrelated resident workloads.

## Evidence

- `src/fam_os/product/model_residency.py`
- `src/fam_os/product/service.py`
- `src/fam_os/scheduler/residency_service.py`
- `tests/unit/test_product_model_residency.py`
- `tests/unit/test_expert_residency_service.py`
- `tests/architecture/test_product_composition_boundary.py`
- `tests/integration/test_product_service.py`
