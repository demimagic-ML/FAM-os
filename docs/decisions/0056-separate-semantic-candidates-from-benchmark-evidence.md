# ADR 0056: Separate semantic candidates from benchmark evidence and policy

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Expert packages need semantic discovery beyond exact capability names and need
measured quality evidence beyond a self-declared tier. Combining an embedding,
benchmark score, and final route into one opaque value would make it impossible
to explain why an expert was considered, whether repair context was disclosed,
or whether a quality claim came from the correct hardware profile.

## Decision

Define separate strict routing-embedding and benchmark-run documents. Bind both
to exact expert package coordinates. Compare only normalized vectors in the
same named embedding space and dimension. Restrict semantic matching to enabled
installed coordinates and exact required capabilities, but return matches as
evidence rather than selection decisions.

Represent benchmark attempts individually, including initial/repair/escalation
kind, disclosure level and digest, conformance failures, verification outcome,
tokens, latency, and complete resource availability. Bind summaries to the
SHA-256 digest of retained raw evidence. Keep run IDs immutable and validate
cross-links from embeddings.

Encode the stable-toposort strong-model regression as an explicit validation
policy while leaving general benchmark contracts task-neutral.

## Consequences

- Similarity cannot bypass installation, capability, or later routing policy.
- Benchmark success cannot erase failed attempts or disclosed verifier context.
- Full-host claims fail when any required CPU/RAM/VRAM/model/storage measurement
  is absent.
- Laguna and Gemma can be compared under one strict envelope without mixing
  their independent runs.
- Embedding generators remain replaceable behind `RoutingTextEmbedder`.
- Two schema roots increase the catalog to 50 documents.
- Phase 9 can add quality/cost policy without changing raw Phase 6 evidence.

## Alternatives considered

1. Store one free-form quality score: rejected because attempt, verifier, and
   hardware provenance would be lost.
2. Let nearest-neighbor rank directly select an expert: rejected because trust,
   compatibility, resource, and verification policy are independent gates.
3. Compare vectors from different generators by dimension alone: rejected
   because coordinate systems are not semantically interchangeable.
4. Embed raw prompts and trusted tests in metadata: rejected because digests are
   sufficient linkage and avoid duplicating sensitive benchmark content.
5. Treat historical strong-model artifacts as installed-package evidence:
   rejected because Phase 6 must exercise the new package lifecycle.

## Evidence

- `src/fam_os/experts/routing_metadata.py`
- `src/fam_os/experts/routing_index.py`
- `src/fam_os/experts/benchmark_metadata.py`
- `src/fam_os/experts/benchmark_index.py`
- `src/fam_os/experts/metadata_validation.py`
- `src/fam_os/routing/semantic_candidates.py`
- `tests/unit/test_expert_routing_benchmark_metadata.py`
- `schemas/v1alpha1/fam.expert.*.schema.json`
