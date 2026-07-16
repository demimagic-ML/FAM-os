# ADR 0013: Provider-neutral Application Fabric Python contracts

**Status:** Accepted  
**Date:** 2026-07-16

## Context

ADR 0003 made Universal Application Fabric a primary boundary, and ADR 0012 placed MCP behind that boundary as one connector protocol. Phase 2 still lacked executable domain types for application identity, capability registration, observations, scoped authority, confirmation, reversible action preparation, postconditions, results, and connector transport.

Building a VS Code extension first would force transport or VS Code SDK concepts to become accidental FAM_OS contracts. A generic contract set without a concrete workflow could instead remain too abstract to prove useful.

## Decision

The `fam_os.applications` component owns immutable standard-library Python contracts for:

- Stable application and running-instance identity.
- Observation and action capability descriptors and registry entries.
- Scoped, expiring, revocable permission grants.
- Immutable structured observation requests and results.
- Prepared action previews, confirmation decisions, reversibility, preconditions, postconditions, deterministic evidence, and terminal results.
- Versioned connector registration plus provider-neutral connector-transport and capability-registry ports.

The initial contract family is `fam.applications/v1alpha1`. This identifies the Python contract generation but is not yet a stable external wire schema.

Construction enforces core safety invariants. Failed observations cannot expose payload. Action capabilities and proposals require deterministic postconditions. Reversible proposals name a reversal capability. Irreversible actions always require confirmation. Verified action results require passing evidence.

A VS Code-shaped fake connector is the first vertical slice. It observes the active editor and prepares a reversible workspace edit guarded by document-version preconditions and document-hash/workspace-test postconditions. No VS Code or MCP type enters the domain.

Concrete local native, MCP, accessibility, OS-tool, and screen/input implementations must satisfy the same `ConnectorTransport` port. Concrete transport and serialized-schema decisions remain separate.

## Consequences

- The real VS Code extension can be implemented against a tested application contract rather than define policy ad hoc.
- Core can reason about MCP and non-MCP capabilities uniformly.
- Capability discovery remains distinct from permission and confirmation.
- Observation and action are distinct request/result families.
- Action preparation is distinct from confirmed execution.
- Connector payloads are frozen and limited to JSON-compatible data.
- Phase 2.7 must define serialization and compatibility before cross-process production use.
- Phase 4 must match result evidence to the approved proposal before releasing success.
- Phase 5 must implement an authenticated local transport and registry without changing these domain meanings.

## Alternatives considered

1. Prototype the VS Code extension first: rejected because SDK and transport shapes would become accidental domain contracts.
2. Use MCP wire types as the domain model: rejected by ADR 0012 because other application integration levels must remain first class.
3. Use untyped dictionaries throughout: rejected because invalid authority, reversibility, result, and evidence combinations would cross the Core boundary.
4. Put all application types in one module: rejected because identity, capability, permission, observation, action, payload, and connector responsibilities evolve independently.
5. Implement a production capability registry now: deferred to Phase 5.1; Phase 2 defines its port and uses a fake.

## Evidence

- `docs/protocols/APPLICATION_CONTRACTS.md` documents the contract family and first VS Code profile.
- Focused unit tests validate identity, capability, permission, observation, action, evidence, registration, and complete fake-connector flow.
- `src/fam_os/applications/` contains no VS Code SDK or MCP imports.
