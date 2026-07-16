# Local Expert Registry

## Purpose

Phase 6.2 provides a deterministic local catalog of expert package manifests.
It answers which current manifests are discoverable by exact package
coordinate, expert identity, capability, tier, or publisher. It does not claim
that a package is installed, enabled, trusted, hardware-compatible, active, or
successful on a benchmark.

## Boundary

```text
bounded manifest source
  -> strict schema decoding
  -> LocalExpertRegistry.refresh
  -> atomic immutable indexes and revision event
  -> Expert Fabric discovery queries
```

`ExpertManifestSource` is the replaceable read port. The first adapter,
`DirectoryExpertManifestSource`, reads one non-recursive configured directory.
The registry imports no filesystem, Ollama, scheduler, signature, or package
installation implementation.

## Coordinates and versions

A catalog entry is identified by `(package_id, package_version)`. Multiple
versions of the same `expert_id` may be present simultaneously so a later
install/update/rollback lifecycle can reason about them explicitly. Phase 6.2
does not choose an active version.

The same coordinate cannot appear twice. Once a coordinate exists, refreshing
different manifest content at that coordinate fails atomically; authors must
publish a new version. An identical refresh is idempotent and does not advance
the revision or emit an event.

## Indexes and matching

Every successful refresh rebuilds these immutable views under one lock:

- exact package coordinate;
- all versions by `expert_id`;
- exact `fam.expert.capabilities/v1` capability;
- publisher identity.

Results have deterministic `(expert_id, package_id, package_version)` ordering.
Capability queries preserve ADR 0051 exact matching. A `code` declaration is
not returned for `code.generate.python`, and no registry query infers a parent,
alias, wildcard, quality, or trust level.

## Atomic refresh and events

The source is completely decoded and duplicate-checked before registry state is
locked. Under the lock, the registry detects coordinate mutations, constructs a
timezone-bearing revision event, and swaps all indexes together. Event creation
failure leaves state unchanged. Concurrent refreshes serialize without partial
indexes.

Each event lists added and removed `ExpertPackageCoordinate` values. Events are
process-local discovery evidence, not a durable security audit. Package
installation and audit persistence belong to later Phase 6 lifecycle work.

## Filesystem source safety

The directory adapter:

- accepts only top-level `*.json` files in deterministic name order;
- bounds file count and bytes per document;
- opens with `O_NOFOLLOW` when the platform provides it;
- accepts regular UTF-8 files only;
- uses the strict shared schema decoder;
- accepts only current `ExpertManifest` (`v1alpha2`) roots.

Legacy `v1alpha1` documents require the explicit migration from Phase 6.1.
Other schema families, malformed JSON, unknown fields, and oversized documents
fail the whole refresh. No partial catalog is published.

## Deferred policy

- Phase 6.3 validates licenses, package digests, signatures, publisher identity,
  and effective trust before installation admission.
- Phase 6.4 evaluates resource and hardware compatibility.
- Phase 6.5 owns durable install state, enabled/disabled selection, update,
  rollback, and removal.
- Phase 6.6 adds routing embeddings and benchmark evidence.

Discovery alone never makes an expert eligible for activation.
