# ADR 0055: Durable side-by-side expert package lifecycle

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Expert manifests are discoverable, trust can be derived, and compatibility can
be evaluated, but no durable state previously distinguished installed,
enabled, retained, or removed versions. Updating one artifact in place would
destroy rollback evidence, and deleting an artifact before a metadata commit
could leave durable state pointing at missing bytes.

## Decision

Create `fam.registry.lifecycle/v1alpha1` installation state and
`ExpertPackageLifecycle`. Keep versions side by side under immutable
coordinates. Require exact accepted trust and non-incompatible compatibility
evidence before staging. Store both observed artifact and canonical signed
manifest digests. Permit at most one enabled coordinate per expert.

Use revision compare-and-swap for durable state. Stage and verify artifacts
before install/update state commits. Re-hash retained artifacts before
rollback. For removal, commit a durable pending-deletion tombstone before
physical deletion, then clear it in a separate cleanup revision. Recovery
retries tombstones after interruption.

A currently constrained package may be installed but cannot be enabled. A
constrained update therefore cannot displace the last active known-good
version. Runtime activation and live placement remain outside Registry.

## Consequences

- Process restart preserves all package choices and audit history.
- Updates preserve rollback bytes and never overwrite a coordinate.
- Interrupted deletion is explicit and recoverable.
- Concurrent writers fail through revision CAS instead of silently losing an
  update.
- A crash after staging but before state commit can leave an unreferenced
  coordinate artifact; it cannot become active without a later valid commit.
- The schema catalog increases to 48 strict roots.
- Runtime adapters must verify and activate the enabled package in later Phase
  6 work; enabled metadata alone does not claim a running model.

## Alternatives considered

1. Replace the active artifact in place: rejected because rollback and digest
   identity would be lost.
2. Delete the old version immediately after update: rejected because it removes
   the last known-good recovery path.
3. Delete bytes before removal state: rejected because commit failure would
   leave a dangling installed record.
4. Treat temporary resource pressure as incompatibility: rejected because it
   would prevent safe preinstallation while the host is busy.
5. Put filesystem copying and JSON mechanics in lifecycle policy: rejected;
   both remain behind replaceable ports.

## Evidence

- `src/fam_os/registry/lifecycle.py`
- `src/fam_os/registry/lifecycle_contracts.py`
- `src/fam_os/registry/lifecycle_ports.py`
- `src/fam_os/adapters/filesystem/package_lifecycle.py`
- `tests/unit/test_expert_package_lifecycle.py`
- `schemas/v1alpha1/fam.registry.installation-state.schema.json`
