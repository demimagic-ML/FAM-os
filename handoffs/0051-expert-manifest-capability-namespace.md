# Handoff 0051: Expert manifest and capability namespace

**Date:** 2026-07-16  
**Plan step:** Phase 6.1  
**Status:** Complete  
**Previous handoff:** `0050-cross-application-acceptance.md`

## Objective

Finalize the installable expert manifest and capability identity rules without
silently changing the already-published exact `v1alpha1` decoder.

## Scope completed

- A bounded canonical `fam.expert.capabilities/v1` parser shared by installable
  `ExpertManifest` and live `ExpertDescriptor` contracts.
- Eleven FAM-owned domains covering kernel, routing, language, code, retrieval,
  math, application, vision, speech, safety, and verification specialists.
- Exact capability matching with no implicit parent, prefix, alias, or wildcard
  expansion.
- A publisher-bound `vendor.<publisher>.<domain>.<operation>...` extension
  branch.
- Frozen `fam.expert.manifest/v1alpha1` decoding through
  `ExpertManifestV1Alpha1` and a fixed compatibility fixture.
- Finalized `fam.expert.manifest/v1alpha2` emission and strict semantic
  validation through the current `ExpertManifest` type.
- An explicit `migrate_expert_manifest_v1alpha1` conversion that rejects
  noncanonical legacy claims rather than guessing replacements.
- Multi-alpha schema descriptor admission and version-owned generated schema
  artifact directories.

## Explicitly not completed

- Registry persistence, indexes, transactions, or installation state; Phase 6.2
  owns those behaviors.
- Cryptographic digest/signature verification or license policy; Phase 6.3 owns
  package trust.
- Hardware compatibility admission, lifecycle operations, benchmark metadata,
  or concrete expert packages; Phases 6.4-6.7 own those concerns.
- Prefix matching or capability inference; exact identity is the deliberate
  policy.

## Architecture and decisions

ADR 0051 introduces the first deliberate side-by-side serialized contract
versions. The old decoder is preserved because adding namespace rejection to
`v1alpha1` would violate ADR 0018. The new version changes semantic admission,
not provider neutrality or the manifest's field layout. Capability declaration
remains an untrusted static package claim and does not confer verifier trust,
application authority, hardware compatibility, or benchmark quality.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/experts/capabilities.py` | Canonical IDs, domains, parsing, and exact matching. |
| `src/fam_os/experts/manifest.py` | Current `v1alpha2` manifest and namespace enforcement. |
| `src/fam_os/experts/legacy_manifest.py` | Frozen `v1alpha1` domain contract. |
| `src/fam_os/experts/migration.py` | Explicit legacy-to-current conversion. |
| `src/fam_os/experts/contracts.py` | Shared live-descriptor capability validation. |
| `src/fam_os/schemas/descriptor.py` | Registered multi-alpha descriptor identities. |
| `src/fam_os/schemas/catalog.py` | Side-by-side expert schema descriptors. |
| `tools/render_contract_schemas.py` | Version-owned schema rendering and stale checks. |
| `schemas/v1alpha1/fam.expert.manifest.schema.json` | Frozen legacy schema artifact. |
| `schemas/v1alpha2/fam.expert.manifest.schema.json` | Finalized expert schema artifact. |
| `docs/protocols/EXPERT_CAPABILITY_NAMESPACE.md` | Canonical namespace protocol. |
| `docs/decisions/0051-versioned-expert-capability-namespace.md` | Compatibility and matching decision. |
| `tests/unit/test_package_expert_manifests.py` | Namespace, vendor, matching, and migration tests. |
| `tests/contract/test_schema_compatibility.py` | Side-by-side exact decoding test. |

## Public interfaces

- `EXPERT_CAPABILITY_NAMESPACE_VERSION`
- `BUILT_IN_CAPABILITY_DOMAINS`
- `ExpertCapabilityId`
- `parse_expert_capability_id`
- `require_expert_capabilities`
- `capability_satisfies`
- `ExpertManifestV1Alpha1`
- `migrate_expert_manifest_v1alpha1`
- `ExpertManifest` now emits `fam.expert.manifest/v1alpha2`

## Validation

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
python3 <AST module/function size gate>
```

Result: 43 generated Draft 2020-12 schemas validated. Both Python environments
passed 558 tests with three expected environment-dependent skips each.
Compileall passed. The size gate found no implementation file above 300 lines
and no Python function above 50 lines across 336 inspected implementation files.
Larry indexed 787 files and 2,434 symbols with 11,084 graph nodes / 42,199
edges; freshness and verification were clean. The persisted code knowledge graph
was refreshed to 11,084 nodes / 42,279 edges.

## Evidence and artifacts

- `schemas/v1alpha1/fam.expert.manifest.schema.json`
- `schemas/v1alpha2/fam.expert.manifest.schema.json`
- `tests/fixtures/schema_compatibility/v1alpha1/expert-manifest.valid.json`
- `docs/protocols/EXPERT_CAPABILITY_NAMESPACE.md`
- `docs/decisions/0051-versioned-expert-capability-namespace.md`

## Known limitations and risks

- The vendor branch requires a single canonical publisher token; Phase 6.3 must
  align package publisher-ID validation with this invariant before third-party
  installation is enabled.
- Exact capability identity does not yet have a persistent lookup index; Phase
  6.2 must implement atomic registry queries and collision policy.
- Capability claims have no quality evidence until benchmark metadata and
  initial package definitions are implemented in Phases 6.6-6.7.

## Operational notes

No process, service, model, port, machine configuration, or user data changed.
Schema generation now takes `schemas/` as its root and writes each registered
version into its own `v1alpha*` directory.

## Recommended next entry point

Begin Phase 6.2. Read `src/fam_os/experts/ports.py`, the current and legacy
manifests, `src/fam_os/registry/`, ADR 0051, and the Application Capability
Registry for atomic-snapshot precedent. Define local registry state and query
contracts before choosing a persistence adapter.
