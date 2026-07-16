# Handoff 0056: Durable expert package lifecycle

**Date:** 2026-07-16  
**Plan step:** Phase 6.5  
**Status:** Complete  
**Previous handoff:** `0055-strong-model-regression-requirement.md`

## Objective

Implement durable install, update, disable, rollback, and remove behavior that
consumes exact trust and compatibility evidence, retains the last known-good
artifact, and recovers safely from interrupted physical deletion.

## Scope completed

- Strict `fam.registry.installation-state/v1alpha1` persistent state.
- Exact manifest, validation-report, compatibility-report coordinate admission.
- Immutable no-follow SHA-256 artifact ingestion behind a replaceable port.
- Canonical signed-manifest digest retention to reject changed content under an
  installed coordinate.
- Side-by-side update with one enabled version per expert.
- Temporarily constrained install/update without displacing an active version.
- Idempotent disable and integrity-rechecked rollback.
- Active-package removal prohibition.
- Metadata-first removal with durable pending-deletion tombstones and explicit
  restart recovery.
- Cross-process file locking, revision compare-and-swap, fsync, and atomic state
  replacement.

## Explicitly not completed

- Runtime-specific model activation; Phase 6.7 supplies concrete package and
  runtime adapter definitions.
- Live placement, context allocation, transfer accounting, or eviction; Phase
  7 owns those decisions.
- Key-revocation response for already installed packages and long-term event
  archival remain Phase 14 hardening concerns.

## Architecture and decisions

ADR 0055 establishes side-by-side immutable coordinates and a durable
installation-state source of truth. Artifacts are staged before install/update
commits. Removal commits a tombstone before deleting bytes, so state never
references prematurely deleted data. Compatibility pressure can prevent
activation without preventing safe preinstallation.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/registry/lifecycle_contracts.py` | Persistent package, event, and removal contracts. |
| `src/fam_os/registry/lifecycle_ports.py` | State and artifact persistence ports. |
| `src/fam_os/registry/lifecycle.py` | Lifecycle admission and state transitions. |
| `src/fam_os/adapters/filesystem/package_lifecycle.py` | Atomic local state and immutable artifacts. |
| `src/fam_os/schemas/catalog.py` | Registers installation-state schema. |
| `schemas/v1alpha1/fam.registry.installation-state.schema.json` | Generated strict schema. |
| `tests/unit/test_expert_package_lifecycle.py` | Lifecycle, restart, integrity, and recovery tests. |
| `tests/contract/schema_manifest_fixtures.py` | Representative state round trip. |
| `docs/protocols/EXPERT_PACKAGE_LIFECYCLE.md` | Public lifecycle semantics. |
| `docs/decisions/0055-durable-side-by-side-expert-package-lifecycle.md` | Durable storage decision. |

## Public interfaces

- `PACKAGE_LIFECYCLE_CONTRACT_VERSION`
- `ExpertPackageInstallationState`
- `InstalledExpertPackage`
- `PackageLifecycleEvent`
- `PendingArtifactRemoval`
- `ExpertPackageLifecycle.install/update/disable/rollback/remove/recover`
- `PackageLifecycleStateStore`
- `InstalledPackageArtifactStore`
- `JsonPackageLifecycleStateStore`
- `ImmutablePackageArtifactStore`

## Validation

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src:. python3 -m compileall -q src tests tools
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
python3 <AST implementation file/function size gate>
```

Result before the final documentation-only edits: all 48 schemas and
compileall passed. Both Python environments passed 583 tests with three
expected environment-dependent skips. The focused lifecycle suite passed seven
tests. The size gate found no source file above 300 lines and no function above
50 lines across 314 implementation files. Larry indexed 830 files / 2,554
symbols with 11,577 nodes / 44,957 edges; freshness and verification were
clean. The code knowledge graph was independently refreshed to the same
11,577-node / 44,957-edge source view.

## Evidence and artifacts

- `schemas/v1alpha1/fam.registry.installation-state.schema.json`
- `tests/unit/test_expert_package_lifecycle.py`
- `docs/protocols/EXPERT_PACKAGE_LIFECYCLE.md`
- `docs/decisions/0055-durable-side-by-side-expert-package-lifecycle.md`

## Known limitations and risks

- A crash or CAS conflict after artifact staging but before state commit may
  leave an unreferenced coordinate artifact. It is never enabled without a
  valid state commit; later maintenance should garbage-collect such artifacts.
- Lifecycle events remain in the state document for this phase. Production
  retention/archival must preserve audit continuity without unbounded state.
- Enabled means selected installation metadata, not a claim that a runtime is
  loaded or healthy.

## Operational notes

Tests used temporary directories only. No downloaded model, Ollama state,
system service, port, hardware setting, or user package was changed.

## Recommended next entry point

Begin Phase 6.6. Read handoff 0026, ADR 0027, the verified smoke report
contracts, routing contracts, and this lifecycle state. Define benchmark and
routing-embedding metadata without coupling benchmark observations to runtime
selection policy.
