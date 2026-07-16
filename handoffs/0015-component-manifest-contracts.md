# Handoff 0015: Component-owned manifest contracts

**Date:** 2026-07-16  
**Plan step:** Phase 2.3  
**Status:** Complete  
**Previous handoff:** `0014-hardware-resource-contracts.md`

## Objective

Define separate versioned expert, verifier, connector, and memory-record manifests with shared package identity where appropriate, while keeping provider mechanisms, live state, permission grants, and persistence engines outside static manifests.

## Scope completed

- Added registry-owned package identity, version, publisher, license, artifact digest, declared trust, and signing-key metadata.
- Required signed package claims to identify a signing key and prevented local-unverified packages from claiming one.
- Added `fam.expert.manifest/v1alpha1` for capability, tier, runtime contract, artifacts, resource requirements, architecture support, and required verifiers.
- Kept expert manifests separate from live `ExpertDescriptor` and `ExpertState`.
- Added `fam.verifier.manifest/v1alpha1` for acceptance/candidate/evidence schemas, determinism, timeout, network policy, and required isolation capabilities.
- Replaced an initially considered concrete sandbox enum with provider-neutral isolation capability IDs during design review.
- Prevented deterministic verifiers from requiring network access.
- Added `fam.connector.manifest/v1alpha1` for static application support, capability descriptors, transport protocol IDs, requested authorities, sandbox profile, and dynamic-capability declaration.
- Required connector authority requests to cover every statically declared capability without treating the request as a grant.
- Kept connector manifests separate from live application instances and `ConnectorRegistration`.
- Added `fam.memory.record/v1alpha1` for content integrity metadata, record kind, explicit owner/purpose/application/workspace/session scope, provenance lineage, sensitivity, retention, and expiry.
- Required derived memory to identify parent records, prohibited self-derivation, and required session scope for session/working memory.
- Kept record content and storage-engine locators out of memory manifests.
- Added focused tests, protocol documentation, ADR 0016, ownership documentation, and plan/status updates.

## Explicitly not completed

- No serialized JSON schema, encoder, decoder, unknown-field policy, or cross-version migration was added; that is Phase 2.7.
- No signature was cryptographically verified and no package was installed, trusted, enabled, updated, or rolled back.
- No manifest registry or persistence layer was implemented.
- No expert compatibility, activation, or residency behavior changed.
- No verifier package was selected or executed from a manifest.
- No connector process, local transport, MCP session, or VS Code extension was created.
- No permission grant was issued from a connector's requested authorities.
- No memory content was stored, retrieved, encrypted, expired, or deleted.

## Architecture and decisions

ADR 0016 keeps manifest vocabulary with the owning fabric rather than creating a global optional-field manifest. Expert, verifier, and connector manifests compose only a small registry-owned `PackageMetadata` fragment. Memory records use their own content digest because user data is not an installable software artifact.

Static manifest claims are not live state. In particular, declared trust is not verified trust, requested authority is not permission, a runtime contract is not an active model, and memory scope is not retrieval authorization.

The verifier manifest states required isolation capabilities rather than an adapter identity. This prevents Bubblewrap, containers, or another runner from entering the public manifest family. Connector protocols are string identities and may include MCP or a native protocol without replacing Application Fabric capability and permission contracts.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/registry/package.py` | Shared package identity, digest, license, and declared-trust metadata |
| `src/fam_os/registry/__init__.py` | Public registry metadata exports |
| `src/fam_os/experts/manifest.py` | Versioned expert package and resource requirements |
| `src/fam_os/experts/__init__.py` | Public expert manifest exports |
| `src/fam_os/verification/manifest.py` | Versioned verifier requirements and determinism policy |
| `src/fam_os/verification/__init__.py` | Public verifier manifest exports |
| `src/fam_os/applications/manifest.py` | Versioned static connector package manifest |
| `src/fam_os/applications/__init__.py` | Public connector manifest exports |
| `src/fam_os/memory/manifest.py` | Versioned permissioned memory-record metadata |
| `src/fam_os/memory/__init__.py` | Public memory manifest exports |
| `tests/unit/test_package_expert_manifests.py` | Package and expert manifest invariants |
| `tests/unit/test_verifier_connector_manifests.py` | Verifier and connector boundary tests |
| `tests/unit/test_memory_record_manifest.py` | Memory scope, provenance, retention, and integrity tests |
| `docs/protocols/MANIFEST_CONTRACTS.md` | Manifest-family and static/live boundary reference |
| `docs/decisions/0016-component-owned-manifest-contracts.md` | Manifest ownership decision |
| `src/fam_os/experts/README.md` | Expert manifest ownership |
| `src/fam_os/verification/README.md` | Verifier manifest ownership |
| `src/fam_os/applications/README.md` | Static versus live connector boundary |
| `src/fam_os/memory/README.md` | Memory record metadata boundary |
| `src/fam_os/registry/README.md` | Package metadata and trust-claim boundary |
| `MASTER_PLAN.md` | Phase 2.3 completion evidence and Phase 2.6 entry point |
| `README.md` | Current implementation and next-step status |
| `handoffs/README.md` | Handoff sequence entry |
| `handoffs/0015-component-manifest-contracts.md` | This implementation record |

## Public interfaces

- `ArtifactDigest`
- `PackageMetadata`
- `PackageTrustLevel`
- `EXPERT_MANIFEST_CONTRACT_VERSION`
- `ExpertResourceRequirements`
- `ExpertManifest`
- `VERIFIER_MANIFEST_CONTRACT_VERSION`
- `DeterminismClass`
- `VerifierManifest`
- `CONNECTOR_MANIFEST_CONTRACT_VERSION`
- `ConnectorManifest`
- `MEMORY_RECORD_MANIFEST_CONTRACT_VERSION`
- `MemoryRecordKind`
- `MemorySensitivity`
- `MemorySourceKind`
- `MemoryContentDigest`
- `MemoryScope`
- `MemoryProvenance`
- `MemoryRecordManifest`

Existing live `ExpertDescriptor`, `ExpertState`, `VerificationRequest`, `VerificationReport`, `ConnectorRegistration`, and permission contracts remain unchanged.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_package_expert_manifests \
  tests.unit.test_verifier_connector_manifests \
  tests.unit.test_memory_record_manifest -v
```

Result: all 20 focused package and manifest tests passed in 0.001 seconds; 0 failures. The first fixture run exposed use of a nonexistent `ConfirmationPolicy.POLICY` enum member; the fixture was corrected to the established `WHEN_REQUIRED` contract and the complete focused suite then passed.

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
```

Result: all 176 FAM_OS tests passed in 0.037 seconds; 0 failures. The previous suite contained 156 tests.

```bash
python3 -m compileall -q src tools tests
```

Result: completed successfully.

```bash
rg -n "Ollama|ollama|Bubblewrap|bubblewrap|MCP|vscode|systemd|subprocess" \
  src/fam_os/experts/manifest.py \
  src/fam_os/verification/manifest.py \
  src/fam_os/applications/manifest.py \
  src/fam_os/memory/manifest.py \
  src/fam_os/registry/package.py
```

Result: no inference provider, sandbox adapter, connector protocol, editor SDK, service manager, or process dependency was found.

```bash
find src/fam_os -name '*.py' -print0 | xargs -0 wc -l | sort -nr | head -n 12
```

Result: the largest new module is `memory/manifest.py` at 137 lines. All new implementation modules remain below the 300-line target and functions remain below the 50-line target.

## Evidence and artifacts

- `docs/protocols/MANIFEST_CONTRACTS.md`
- `docs/decisions/0016-component-owned-manifest-contracts.md`
- `tests/unit/test_package_expert_manifests.py`
- `tests/unit/test_verifier_connector_manifests.py`
- `tests/unit/test_memory_record_manifest.py`
- Provider-neutral boundary: `docs/decisions/0002-provider-neutral-contract-boundaries.md`
- Application boundary: `docs/decisions/0013-application-fabric-python-contracts.md`

## Known limitations and risks

- Manifest version markers are Python contract identifiers, not serialized wire compatibility.
- Artifact digest shape is validated, but algorithm policy and digest verification are not implemented.
- Package versions are non-empty opaque strings; semantic-version parsing and compatibility ranges remain future registry policy.
- Package trust is a declared claim until signature and publisher policy verify it.
- Expert runtime contract IDs, artifact IDs, capability namespaces, and verifier IDs are syntactic identifiers until registries validate references.
- Verifier isolation capability IDs have no resolver or minimum-strength ordering yet.
- Connector manifests declare maximum capabilities, but install-time review, runtime registration reconciliation, and permission admission are not implemented.
- Memory manifests carry privacy-sensitive identifiers in real deployments; persistence, encryption, export, deletion, and multi-user isolation remain Phase 10 work.
- Memory expiry is metadata only until a retention service enforces it.

## Operational notes

This change is immutable Python metadata contracts, documentation, and in-memory tests only. It downloaded and installed no package, verified no signature, started no expert or connector, invoked no model or verifier, and persisted no memory content.

## Recommended next entry point

Begin Phase 2.6. Read this handoff, Core result/plan contracts, Application Fabric result contracts, inference/verification ports, and scheduler effective-budget contracts. Define a shared structured error envelope and explicit degradation records while preserving component-owned evidence. Provider exceptions, command output, secrets, and raw connector sessions must not cross the boundary.
