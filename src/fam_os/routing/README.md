# Routing ownership

Owns route names, capability and complexity decisions, and router evaluation policy.

Routing request and result Python contracts use the `fam.routing/v1alpha1` family marker. Required capabilities are normalized and unique. See `docs/protocols/CORE_CONTRACTS.md` and ADR 0014.

It does not allocate hardware. Routing implementations accept `RoutingRequest` and return `RoutingResult`; the scheduler and Core decide how to execute the typed decision.

`ModelTaskRouter` is a provider-neutral policy over `InferenceRuntime`. It owns the routing prompt and deterministic parser, requests JSON output, and records inference metrics without importing Ollama. A malformed response with no supported route is an explicit parse error.

`routing/evaluation.py` owns the typed four-route parity workload, per-case evidence, and aggregate summaries. Artifact writing and historical fixture parsing remain benchmark-tool responsibilities outside the runtime package.

`SemanticExpertCandidateFinder` uses a replaceable text embedder and the Expert
Fabric routing index to return cosine-similarity evidence only for enabled,
capable package coordinates. It does not turn similarity into final policy.
