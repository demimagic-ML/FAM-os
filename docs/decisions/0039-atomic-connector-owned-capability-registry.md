# ADR 0039: Make connector registration the atomic capability ownership unit

**Status:** Accepted  
**Date:** 2026-07-16

## Decision

Index Application Fabric capabilities by global entry ID and instance/capability
pair, with each connector registration owning one replaceable set. Validate all
foreign collisions and construct the change event before atomically swapping
registrations/indexes/revision. Expose immutable sorted snapshots and revisioned
events without choosing a transport.

## Consequences

- Connector reconnect can replace stale capabilities without partial visibility.
- One connector cannot take over another connector's instance or capability.
- Readers can deterministically resynchronize from snapshots plus revisions.
- Persistence and authenticated registration remain Phase 5.2/productization.

## Evidence

- `src/fam_os/applications/registry.py`
- `tests/unit/test_application_capability_registry.py`
- `docs/protocols/APPLICATION_CAPABILITY_REGISTRY.md`
