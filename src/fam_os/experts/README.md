# Experts ownership

Owns expert identity, capabilities, tiers, manifests, lifecycle states, and activation interfaces.

It does not know Ollama endpoints or cgroup paths. Runtime and operating-system mechanics belong in adapters.

`ExpertCatalog` is the lookup port used by Core and scheduler-facing application policy. Phase 1.9 defines the port only; installable registry persistence remains Phase 6.

`ExpertManifest` is the finalized `fam.expert.manifest/v1alpha2`
installed-package declaration. It uses the exact
`fam.expert.capabilities/v1` namespace while retaining provider-neutral runtime,
artifact, resource, license/trust, and verifier declarations. The frozen
`ExpertManifestV1Alpha1` root and explicit migration preserve old documents.
Live `ExpertDescriptor` and `ExpertState` remain separate. See
`docs/protocols/EXPERT_CAPABILITY_NAMESPACE.md`, ADR 0016, and ADR 0051.

`LocalExpertRegistry` is the Phase 6.2 atomic discovery index. It retains
side-by-side package versions and supports exact queries without selecting an
active version or conferring package trust. Local files enter through the
replaceable `ExpertManifestSource` port. See
`docs/protocols/LOCAL_EXPERT_REGISTRY.md` and ADR 0052.

`ExpertCompatibilityEvaluator` is the Phase 6.4 pure host/profile check. Its
strict report distinguishes full compatibility, explicit CPU-only fallback,
current contention, and hard incompatibility without choosing a placement. See
`docs/protocols/EXPERT_HARDWARE_COMPATIBILITY.md` and ADR 0054.

Phase 6.6 adds immutable semantic routing embeddings and benchmark-run metadata.
The indexes return similarity and measured-quality evidence; they never select
or activate a package. Cross-document validation binds benchmark runs to the
same package/expert and preserves disclosure, conformance, and full-host
resource evidence. See `docs/protocols/EXPERT_ROUTING_BENCHMARK_METADATA.md`
and ADR 0056.

Phase 6.7 adds exact runtime bindings and installed capability candidates for
the local reference package set. Laguna and Gemma remain escalation-only and
retain complete side-by-side rollback definitions. See
`docs/protocols/REFERENCE_EXPERT_PACKAGES.md` and ADR 0057.
