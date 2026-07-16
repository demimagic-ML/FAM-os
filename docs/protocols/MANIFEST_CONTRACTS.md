# Package and Record Manifest Contracts

## Contract families

Phase 2.3 defined four independent versioned-alpha manifest families. Phase 6.1
adds the first deliberate expert-manifest evolution:

| Family | Owner | Purpose |
|---|---|---|
| `fam.expert.manifest/v1alpha1` | Expert Fabric | Frozen original expert manifest retained for exact decoding and explicit migration |
| `fam.expert.manifest/v1alpha2` | Expert Fabric | Current installable expert manifest with canonical capability namespace |
| `fam.verifier.manifest/v1alpha1` | Verification Fabric | Acceptance/evidence schemas, determinism, isolation capabilities, timeout, and network policy |
| `fam.connector.manifest/v1alpha1` | Application Fabric | Static application/capability declarations, requested authorities, supported protocol IDs, and sandbox profile |
| `fam.memory.record/v1alpha1` | Memory Fabric | Content integrity metadata, owner/purpose scope, provenance, sensitivity, retention, and expiry |

The first three compose registry-owned `PackageMetadata`. The memory record is user data metadata, not an installable package, and therefore has its own content digest and no package identity.

These immutable Python contracts now have strict self-describing JSON roots, generated Draft 2020-12 schemas, exact alpha compatibility, and fixed rejection fixtures. See `SERIALIZED_SCHEMA_COMPATIBILITY.md` and ADR 0018.

## Shared package metadata

`PackageMetadata` records package identity and version, publisher, license identifier, artifact digest, declared trust level, and optional signing-key identity. A signed package must name a signing key, while a local unverified package cannot claim one.

Construction validates the claim's shape; it does not verify a signature,
install an artifact, execute code, or confer trust. Phase 6.3 derives effective
trust through the separate policy, detached-signature, observed-digest, and
validation-report boundary in `PACKAGE_TRUST_VALIDATION.md`. Package lifecycle
remains separate.

## Expert manifests

`ExpertManifest` is installed package metadata, not live residency state. It declares:

- expert identity, display name, and tier;
- capability IDs;
- a provider-neutral runtime contract ID;
- package artifact IDs;
- resident, storage, system-memory, accelerator-memory, architecture, and maximum-context requirements;
- verifier IDs required by acceptance policy.

It contains no Ollama model name, HTTP endpoint, cgroup path, GPU index, or current load state. `ExpertDescriptor` remains the smaller Phase 1 runtime-selection contract until registry composition is implemented.

The current manifest is `v1alpha2` and uses
`fam.expert.capabilities/v1`. IDs have exact matching, FAM-owned domains, and a
publisher-bound vendor branch. The old `v1alpha1` root remains registered as
`ExpertManifestV1Alpha1`; migration is explicit and rejects legacy capability
strings that cannot enter the canonical namespace. See
`EXPERT_CAPABILITY_NAMESPACE.md` and ADR 0051.

## Verifier manifests

`VerifierManifest` declares acceptance IDs, candidate and evidence schema IDs, determinism class, timeout, network policy, and provider-neutral isolation capability IDs. It states requirements such as process limits, filesystem denial, or network denial; it does not name Bubblewrap, a container engine, a compiler executable, or one sandbox adapter.

A verifier that claims deterministic execution cannot require network access. Trust policy and verifier selection remain separate from this static description.

## Connector manifests

`ConnectorManifest` describes the maximum static surface an installed connector package may offer. It declares supported application IDs, typed Application Fabric capability descriptors, protocol identifiers, requested authorities, a sandbox profile, and whether the live capability set may change.

Protocol identifiers are data. MCP, a native extension protocol, or another local transport may appear without becoming the Application Fabric model. Requested authorities must cover the declared capabilities, but the manifest grants none of them. A live `ConnectorRegistration` remains instance-specific and permission evaluation remains a Core policy.

## Memory record manifests

`MemoryRecordManifest` describes a stored record without embedding its content or a storage-engine locator. It records:

- record kind and content schema/media type;
- content byte size and digest;
- an owner plus explicit purpose, application, workspace, and optional session scopes;
- source kind, source identity, creator, capture time, and parent-record lineage;
- sensitivity, retention policy, creation time, and optional expiry.

Derived records require parent provenance and cannot reference themselves. Session and working memory require a session scope. No memory scope is global by default, and no manifest itself authorizes retrieval.

## Static metadata versus live state

Manifests answer what an installed artifact or stored record declares. They do not answer whether a package is installed, enabled, trusted by policy, compatible with current hardware, resident, connected, permitted, expired, or successfully verified. Those states belong to registries, schedulers, Core policy, and lifecycle services in later phases.
