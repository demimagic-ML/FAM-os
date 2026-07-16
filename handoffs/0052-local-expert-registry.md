# Handoff 0052: Local expert registry

**Date:** 2026-07-16  
**Plan step:** Phase 6.2  
**Status:** Complete  
**Previous handoff:** `0051-expert-manifest-capability-namespace.md`

## Objective

Make current expert package manifests locally discoverable through atomic,
deterministic indexes without conflating discovery with trust, installation,
hardware admission, version activation, or runtime residency.

## Scope completed

- `LocalExpertRegistry` with whole-catalog atomic refresh and immutable
  snapshots.
- Exact indexes by package coordinate, expert identity, capability and optional
  tier, and publisher.
- Side-by-side package versions with no implicit newest/active selection.
- Idempotent identical refresh, monotonically revisioned added/removed events,
  and event-construction rollback safety.
- Duplicate coordinate rejection and fail-closed detection of changed content
  reused under an existing package ID/version.
- Concurrency tests proving that readers never receive partially rebuilt
  indexes.
- A replaceable `ExpertManifestSource` port.
- A bounded, non-recursive, no-follow, regular UTF-8 filesystem source using the
  strict shared schema decoder and accepting current `v1alpha2` expert
  manifests only.

## Explicitly not completed

- Digest, signature, license, publisher, and effective trust validation; Phase
  6.3 owns that admission policy.
- Resource or hardware compatibility; Phase 6.4 owns compatibility results.
- Installed/enabled/disabled/active state, update, rollback, or removal; Phase
  6.5 owns durable lifecycle state.
- Routing embeddings, benchmark evidence, or concrete package definitions;
  Phases 6.6-6.7 own those artifacts.

## Architecture and decisions

ADR 0052 makes strict local manifests the reconstructable discovery source and
keeps mutable indexes process-local. Package coordinate, rather than only
`expert_id`, owns uniqueness so multiple versions remain visible for later
rollback. Exact capability semantics from ADR 0051 are preserved. Discoverable
content remains untrusted and cannot be activated merely because it appears in
the registry.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/experts/registry.py` | Atomic indexes, queries, refresh, and events. |
| `src/fam_os/experts/registry_contracts.py` | Package coordinate, snapshot, and event values. |
| `src/fam_os/experts/ports.py` | Replaceable manifest-source port. |
| `src/fam_os/adapters/filesystem/expert_manifests.py` | Bounded strict directory source. |
| `src/fam_os/adapters/filesystem/README.md` | Filesystem adapter ownership. |
| `tests/unit/test_local_expert_registry.py` | Index, version, atomicity, idempotence, and concurrency tests. |
| `tests/integration/test_directory_expert_manifest_registry.py` | Strict local source integration and rejection tests. |
| `docs/protocols/LOCAL_EXPERT_REGISTRY.md` | Registry protocol and deferred-policy boundary. |
| `docs/decisions/0052-atomic-local-expert-manifest-registry.md` | Durable registry decision. |

## Public interfaces

- `ExpertPackageCoordinate`
- `ExpertRegistrySnapshot`
- `ExpertRegistryEvent`
- `coordinate_for`
- `ExpertManifestSource`
- `LocalExpertRegistry.refresh`, `refresh_from`, `lookup`, `versions`,
  `find_by_capability`, `find_by_publisher`, `snapshot`, and `events`
- `DirectoryExpertManifestSource`

## Validation

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
python3 <AST module/function size gate>
```

Result: all 43 schema artifacts and compileall passed. Both Python environments
passed 566 tests with three expected environment-dependent skips each. The size
gate found no implementation file above 300 lines and no Python function above
50 lines across 340 inspected implementation files.
Larry indexed 797 files / 2,463 symbols with 11,153 nodes / 42,686 edges;
freshness and verification were clean. The code knowledge graph was refreshed
to the same 11,153-node / 42,686-edge source view.

## Evidence and artifacts

- `tests/unit/test_local_expert_registry.py`
- `tests/integration/test_directory_expert_manifest_registry.py`
- `docs/protocols/LOCAL_EXPERT_REGISTRY.md`
- `docs/decisions/0052-atomic-local-expert-manifest-registry.md`

## Known limitations and risks

- Directory contents are discoverable, not trusted. No installer may treat this
  registry as sufficient admission evidence before Phase 6.3.
- Version strings have deterministic lexical display order but no precedence
  semantics; lifecycle policy must use validated version rules.
- Events are in-memory discovery history, not the durable package lifecycle
  audit required by later install/update/remove work.

## Operational notes

The filesystem source is read-only. No package directory, process, service,
model, port, machine configuration, or user data was changed.

## Recommended next entry point

Begin Phase 6.3. Read `src/fam_os/registry/package.py`, the strict schema codec,
`LocalExpertRegistry`, ADRs 0016/0018/0051/0052, and existing tamper-evident
audit adapters. Define a validation result and trusted publisher/key boundary
before allowing any discovered manifest into installation admission.
