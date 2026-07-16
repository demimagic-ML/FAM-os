# ADR 0052: Atomic local expert manifest registry over bounded sources

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 6.1 defines package manifests and exact capability identities. Phase 6.2
must make local expert versions discoverable without prematurely combining
discovery with signature trust, hardware admission, installation state,
runtime activation, or routing quality. The eventual package lifecycle also
needs side-by-side versions for rollback.

## Decision

Implement `LocalExpertRegistry` in Expert Fabric as a thread-safe atomic index
of current `ExpertManifest` values. Identify entries by package ID and version,
allow multiple versions per expert, and expose deterministic exact queries by
coordinate, expert, capability/tier, and publisher.

Refresh is whole-catalog and idempotent. Duplicate coordinates and changed
content under an existing coordinate fail before mutation. Successful refresh
rebuilds every index and emits one added/removed revision event. Discovery
events are not treated as durable trust audit records.

Read manifests through the `ExpertManifestSource` port. The first adapter is a
bounded read-only directory source using strict schema decoding, regular-file
checks, size/count limits, and no-follow file opening. It admits current
`v1alpha2` manifests only; legacy migration remains explicit.

## Consequences

- Registry queries cannot partially observe one source refresh.
- Multiple versions are discoverable without incorrectly selecting an active
  version before Phase 6.5.
- Exact capability semantics remain unchanged between manifest and registry.
- Local catalog files survive process restart, while the in-memory indexes are
  safely reconstructed rather than serialized as a second source of truth.
- A discoverable package is not automatically trusted or activatable.
- Phase 6.3 must insert validation before any installer treats catalog content
  as admissible.

## Alternatives considered

1. One mutable map keyed only by `expert_id`: rejected because it erases version
   history and cannot support explicit rollback.
2. Select the newest version lexically: rejected because version interpretation
   and enablement belong to validated package lifecycle policy.
3. Persist internal indexes as another database immediately: rejected because
   strict local manifests are already the reconstructable discovery source and
   install state is not defined until Phase 6.5.
4. Recursively scan arbitrary package trees: rejected because discovery scope,
   resource use, and symlink behavior would be ambiguous.
5. Accept legacy manifests implicitly: rejected because ADR 0051 requires an
   explicit migration and canonical capability review.

## Evidence

- `src/fam_os/experts/registry.py`
- `src/fam_os/experts/registry_contracts.py`
- `src/fam_os/experts/ports.py`
- `src/fam_os/adapters/filesystem/expert_manifests.py`
- `tests/unit/test_local_expert_registry.py`
- `tests/integration/test_directory_expert_manifest_registry.py`
