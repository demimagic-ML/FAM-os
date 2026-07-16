# ADR 0016: Component-owned manifests composed with shared package metadata

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 1 has small live contracts for expert selection, verification requests/results, and connector registration, while Memory Fabric has no record contract. Installable package declarations and stored-record metadata need richer, versioned schemas without turning one global manifest into a god contract or binding FAM to Ollama, Bubblewrap, MCP, VS Code, or a database.

Package identity, license, artifact integrity, and trust claims are common to experts, verifiers, and connectors. Capabilities, resources, authority, isolation, and provenance remain component-specific semantics.

## Decision

FAM_OS defines four component-owned versioned-alpha manifest families. Expert, verifier, connector, and memory modules each own their manifest semantics and validation. Installable expert, verifier, and connector manifests compose small registry-owned `PackageMetadata`; memory records use separate content-integrity metadata because user data is not a software package.

Expert manifests declare provider-neutral runtime contract IDs and resource requirements. Verifier manifests declare provider-neutral isolation capability IDs instead of a concrete sandbox level. Connector manifests declare protocol IDs as replaceable data and reuse Application Fabric capability/authority contracts. Memory records declare content integrity, explicit scope, provenance, retention, sensitivity, and expiry without a database locator or embedded content.

Manifests describe static claims only. They do not represent installation state, signature verification, hardware compatibility, runtime residency, live connector instances, granted permission, retrieval authorization, or verification outcomes.

## Consequences

- Each fabric owns its vocabulary and can evolve independently under an explicit version.
- Registry code can validate common package identity without learning expert, verifier, or connector policy.
- A connector may support MCP without making MCP the internal capability or permission model.
- Verifier requirements remain independent of Bubblewrap or another sandbox implementation.
- Memory metadata is inspectable and deletable by stable record ID without baking a storage engine into the schema.
- Phase 2.7 must define serialized compatibility for all four families and shared package metadata.
- Phase 6 must cryptographically verify signatures and implement install/update/rollback state.
- Phase 8 must finalize verifier trust and execution selection.
- Phase 10 must implement memory persistence, retrieval authorization, expiry, and deletion.

## Alternatives considered

1. One global manifest with optional fields for every component: rejected because it creates a god schema and weak invariants.
2. Put all manifests in `registry/`: rejected because the registry owns package lifecycle, not component capability semantics.
3. Reuse live `ExpertDescriptor` and `ConnectorRegistration`: rejected because installed declarations and live state have different lifecycles.
4. Store Ollama model names, Bubblewrap levels, MCP tool shapes, or database paths: rejected because adapters must remain replaceable.
5. Treat memory records as signed software packages: rejected because user content has different ownership, privacy, retention, and deletion requirements.
6. Mark signed packages trusted at construction: rejected because manifest validation is not cryptographic or policy verification.

## Evidence

- `docs/protocols/MANIFEST_CONTRACTS.md` documents the families and static/live boundary.
- `tests/unit/test_package_expert_manifests.py` covers package identity, trust claims, expert capability, resource, and verifier requirements.
- `tests/unit/test_verifier_connector_manifests.py` covers provider-neutral isolation, determinism/network policy, connector authority coverage, and protocol plurality.
- `tests/unit/test_memory_record_manifest.py` covers explicit scope, provenance lineage, integrity, retention, expiry, and session boundaries.
