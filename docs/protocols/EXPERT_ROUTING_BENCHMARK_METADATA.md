# Expert routing embeddings and benchmark metadata

Phase 6.6 provides semantic candidate evidence and immutable measured-quality
evidence for installed expert packages. These documents do not make a routing,
activation, placement, or acceptance decision by themselves.

## Routing embeddings

`fam.expert.routing-embedding/v1alpha1` binds one embedding to:

- an exact package coordinate, expert, and publisher;
- a named embedding space and generator identity/version;
- an L2-normalized finite vector of 1 through 4,096 dimensions;
- canonical expert capabilities;
- the SHA-256 digest of the source description used to generate it; and
- zero or more exact benchmark run IDs.

Vectors are comparable only when both embedding-space identity and dimension
match. `ExpertRoutingEmbeddingIndex` atomically refreshes immutable identities
and returns deterministic cosine-similarity matches. It filters by required
capability and an explicit set of eligible package coordinates.

`SemanticExpertCandidateFinder` obtains the query vector through the
provider-neutral `RoutingTextEmbedder` port and limits matching to packages
marked enabled in durable installation state. Its output is ranked evidence;
Core routing policy must still consider trust, compatibility, benchmark
quality, current resources, budgets, and verification requirements.

## Benchmark observations

`fam.expert.benchmark-run/v1alpha1` binds a raw evidence digest to one package,
expert, suite version, validation profile, and acceptance policy. It records:

- contiguous initial, repair, and escalation attempts;
- exact model reference for every attempt;
- prompt/output tokens and wall time;
- whether verifier context was undisclosed, examples-only, or trusted tests
  plus examples;
- a SHA-256 digest whenever verifier-owned context was disclosed;
- strict conformance failure codes on failed attempts;
- the single terminal passing attempt, when any; and
- CPU, peak RAM, maximum VRAM, model residency, accelerator residency, and
  storage read/write measurements with exact missing-measurement declarations.

A verified outcome must have exactly one passing final attempt and its kind
must match the outcome. Initial attempts cannot receive verifier disclosure.
Passing attempts cannot retain conformance failures.

`ExpertBenchmarkIndex` preserves immutable run IDs and supports exact package
and suite queries. `validate_routing_benchmark_links` ensures embedding evidence
belongs to the same package and expert.

## Strong-model regression

`require_stable_toposort_regression` enforces the Phase 6 regression envelope:
full-reference workstation measurements, suite/version `stable-toposort/2`,
acceptance policy `stable-toposort-v2`, one unmixed model reference, and all of:

- stable input order;
- neighbor-only initialization;
- cycle rejection;
- input immutability; and
- no `set`, `min`, or `sorted` calls.

Phase 6.7 must create the Laguna and Gemma packages and produce fresh runs
through installed package coordinates. Historical Phase 2 reports remain the
regression floor but are not silently reclassified as package-system runs.

## Storage boundary

Bounded no-follow directory sources decode only the expected strict document
type. Embeddings and benchmark summaries contain digests and measurements, not
prompts, candidate source, trusted tests, user content, or raw hardware
identifiers. Raw evidence stays in separately retained benchmark artifacts.
