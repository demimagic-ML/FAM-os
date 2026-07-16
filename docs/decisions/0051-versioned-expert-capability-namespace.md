# ADR 0051: Versioned exact expert capability namespace

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The original `fam.expert.manifest/v1alpha1` contract represented capabilities
as unique non-empty strings. Phase 6 package discovery and routing require
stable identities, typo rejection, ownership for extensions, and a clear
answer to whether hierarchy implies matching. Tightening the old decoder in
place would violate ADR 0018's exact-version compatibility rule.

## Decision

Keep `v1alpha1` registered and exactly decodable as
`ExpertManifestV1Alpha1`. Introduce `fam.expert.manifest/v1alpha2` as the
current `ExpertManifest`, with the same wire fields and a required
`fam.expert.capabilities/v1` semantic namespace.

Built-in capabilities use bounded lowercase dot-separated IDs beneath owned
domains. Publisher extensions use
`vendor.<publisher-id>.<domain>.<operation>...` and are bound to the manifest's
package publisher. Capability matching is exact; hierarchy and qualifiers do
not create implicit wildcards or authority.

Provide `migrate_expert_manifest_v1alpha1` as the only migration. It revalidates
legacy capabilities and fails visibly when a package author must select a new
canonical identity. Schema generation and exact compatibility admission now
support multiple explicitly registered alpha versions in version-owned
artifact directories.

## Consequences

- Existing `v1alpha1` documents remain decodable and have a fixed fixture.
- New packages cannot silently invent top-level built-in domains or impersonate
  another publisher's extension branch.
- Installable and live expert contracts share one validator.
- A capability claim still conveys neither quality nor trust.
- Phase 6.2 can index exact capability IDs without defining matching semantics.
- Adding an interoperable built-in domain or changing matching requires a new
  decision and namespace version.

## Alternatives considered

1. Tighten `v1alpha1` in place: rejected because it changes exact legacy
   decoding semantics.
2. Treat arbitrary strings as permanent: rejected because typos and collisions
   would become package-discovery behavior.
3. Use prefix or wildcard matching: rejected because capability scope would be
   widened implicitly.
4. Put model names or provider routes in capability IDs: rejected because
   Ollama, llama.cpp, and future runtimes remain adapters.
5. Let vendor packages claim built-in roots: rejected because ownership and
   interoperability would become ambiguous.

## Evidence

- `src/fam_os/experts/capabilities.py`
- `src/fam_os/experts/legacy_manifest.py`
- `src/fam_os/experts/migration.py`
- `schemas/v1alpha1/fam.expert.manifest.schema.json`
- `schemas/v1alpha2/fam.expert.manifest.schema.json`
- `tests/fixtures/schema_compatibility/v1alpha1/expert-manifest.valid.json`
- `tests/unit/test_package_expert_manifests.py`
- `tests/contract/test_schema_compatibility.py`
