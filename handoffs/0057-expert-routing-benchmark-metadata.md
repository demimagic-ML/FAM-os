# Handoff 0057: Expert routing and benchmark metadata

**Date:** 2026-07-16  
**Plan step:** Phase 6.6  
**Status:** Complete  
**Previous handoff:** `0056-durable-expert-package-lifecycle.md`

## Objective

Make semantic expert discovery and measured quality available as explicit,
package-bound evidence while preserving initial/repair outcomes, verifier
disclosure, strict failures, and full-host resource measurements.

## Scope completed

- Strict normalized routing-embedding metadata with exact embedding-space,
  generator, source-digest, capability, package, and benchmark identities.
- Atomic immutable embedding index with deterministic cosine ranking and exact
  space, dimension, capability, and eligible-coordinate filtering.
- Provider-neutral query embedder port and semantic candidate finder restricted
  to enabled durable package state.
- Strict benchmark-run metadata with contiguous attempt kind, model reference,
  disclosure/digest, conformance failures, verification, tokens, and latency.
- Exact CPU, RAM, VRAM, model residency, accelerator residency, and storage
  availability evidence plus raw artifact digest.
- Immutable benchmark index and package/suite queries.
- Cross-document package/expert benchmark-link validation.
- Stable-toposort v2 full-workstation regression policy covering all five strict
  requirement families and preventing mixed-model runs.
- Bounded no-follow strict directory sources for both metadata families.

## Explicitly not completed

- No embedding generator/model package was chosen; Phase 6.7 supplies initial
  concrete packages and adapters remain replaceable.
- Historical Laguna/Gemma reports were not relabeled as installed-package runs.
- Fresh required strong-model package regressions remain Phase 6.7's exit work.
- Similarity and benchmark evidence do not implement final selection policy;
  Phase 9 owns quality/cost selection.

## Architecture and decisions

ADR 0056 separates semantic candidate evidence, benchmark observation, and
final routing policy. Embedding vectors compare only inside one exact space.
Benchmark success cannot hide failed attempts, disclosed tests, missing
measurements, or strict conformance failures. All links bind to exact package
coordinates.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/experts/routing_metadata.py` | Versioned embedding document. |
| `src/fam_os/experts/routing_index.py` | Atomic semantic evidence index. |
| `src/fam_os/experts/benchmark_metadata.py` | Versioned attempt/resource evidence. |
| `src/fam_os/experts/benchmark_index.py` | Immutable benchmark index. |
| `src/fam_os/experts/metadata_validation.py` | Cross-links and strong regression policy. |
| `src/fam_os/routing/semantic_candidates.py` | Enabled-package semantic candidates. |
| `src/fam_os/routing/ports.py` | Provider-neutral text embedder port. |
| `src/fam_os/adapters/filesystem/expert_metadata.py` | Strict bounded metadata sources. |
| `src/fam_os/adapters/filesystem/bounded_documents.py` | Shared no-follow bounded reader. |
| `tests/unit/test_expert_routing_benchmark_metadata.py` | Evidence/index/policy/source tests. |
| `schemas/v1alpha1/fam.expert.routing-embedding.schema.json` | Generated embedding schema. |
| `schemas/v1alpha1/fam.expert.benchmark-run.schema.json` | Generated benchmark schema. |
| `docs/protocols/EXPERT_ROUTING_BENCHMARK_METADATA.md` | Protocol semantics. |
| `docs/decisions/0056-separate-semantic-candidates-from-benchmark-evidence.md` | Durable separation decision. |

## Public interfaces

- `EXPERT_ROUTING_METADATA_VERSION`
- `ExpertRoutingEmbedding`, `RoutingEmbeddingQuery`, `ExpertRoutingMatch`
- `ExpertRoutingEmbeddingIndex`
- `EXPERT_BENCHMARK_METADATA_VERSION`
- `ExpertBenchmarkAttempt`, `ExpertBenchmarkResources`, `ExpertBenchmarkRun`
- `ExpertBenchmarkIndex`
- `RoutingTextEmbedder`, `SemanticExpertCandidateFinder`
- `validate_routing_benchmark_links`
- `require_full_host_evidence`, `require_stable_toposort_regression`
- `DirectoryExpertRoutingEmbeddingSource`, `DirectoryExpertBenchmarkSource`

## Validation

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src:. python3 -m compileall -q src tests tools
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
python3 <AST implementation file/function size gate>
```

Result: all 50 schemas and compileall passed. Both Python environments passed
592 tests with three expected environment-dependent skips. The size gate found
no source file above 300 lines and no function above 50 lines across 322
implementation files. Larry indexed 844 files / 2,606 symbols with 11,790
nodes / 45,924 edges; freshness and verification were clean. The code knowledge
graph was independently refreshed to the same 11,790-node / 45,924-edge source
view.

## Evidence and artifacts

- `schemas/v1alpha1/fam.expert.routing-embedding.schema.json`
- `schemas/v1alpha1/fam.expert.benchmark-run.schema.json`
- `tests/unit/test_expert_routing_benchmark_metadata.py`
- `docs/protocols/EXPERT_ROUTING_BENCHMARK_METADATA.md`
- `docs/decisions/0056-separate-semantic-candidates-from-benchmark-evidence.md`

## Known limitations and risks

- Embedding quality and drift are not established until concrete generators and
  benchmarks exist.
- Resource evidence records boundary/collector observations; sampling precision
  remains a property of the raw benchmark artifact.
- Metadata directories are reconstructable sources, not a remote package index.

## Operational notes

Tests used temporary metadata directories and deterministic fake vectors. No
model, Ollama service, system setting, hardware resource, or user data changed.

## Recommended next entry point

Begin Phase 6.7. Read package manifests, lifecycle, Ollama activation contracts,
the exact installed model inventory, handoff 0026, and this metadata protocol.
Define signed/local policy-conscious language, code, retrieval, and verifier
packages before fresh Laguna/Gemma full-workstation runs.
