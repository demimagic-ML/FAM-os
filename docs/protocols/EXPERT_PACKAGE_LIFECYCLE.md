# Expert package lifecycle

Phase 6.5 owns durable installation state for validated expert packages. It
does not discover manifests, derive trust, choose hardware placement, start an
inference runtime, or decide routing quality.

## Admission

Every install or update consumes three independently produced values:

1. A current `fam.expert.manifest/v1alpha2` manifest.
2. An accepted `fam.registry.trust/v1alpha1` validation report for the exact
   package coordinate and independently observed artifact digest.
3. A `fam.expert.compatibility/v1alpha1` report for the exact package and
   expert under a named hardware profile.

`incompatible` packages are rejected before artifact copying. A
`currently_constrained` package may be retained for later use, but it is never
enabled and an update in that condition does not displace the current
known-good version.

## Durable state

`fam.registry.installation-state/v1alpha1` is the authoritative local state.
It contains:

- all installed package coordinates and immutable artifact locators;
- observed artifact and canonical signed-manifest SHA-256 digests;
- effective trust and policy identity;
- compatibility status and validation profile;
- at most one enabled version per expert;
- pending physical artifact removals; and
- a complete, contiguous revisioned lifecycle event history.

The filesystem state adapter uses an exclusive cross-process lock,
compare-and-swap revision check, a same-directory temporary file, file fsync,
atomic replacement, and directory fsync. A malformed or wrong-schema state
file fails closed.

## Operations

- **Install:** stage and hash the immutable artifact, then commit the first
  version. Compatible packages become enabled; currently constrained packages
  remain installed but disabled.
- **Update:** retain the existing version beside the new version. A compatible
  update atomically becomes enabled and disables the previous version. A
  constrained update leaves the existing enabled version unchanged.
- **Disable:** atomically clears the enabled flag. It is idempotent.
- **Rollback:** re-hash the retained artifact, then atomically enable that
  version and disable the current version of the same expert.
- **Remove:** active versions cannot be removed. State first removes the
  package and records a pending artifact deletion. Physical deletion is then
  attempted and a second cleanup revision clears the pending record.
- **Recover:** retries durable pending artifact deletions after interruption.

The state commit is always later than artifact staging, so a failed commit can
leave only an unreferenced coordinate-owned artifact. Removal reverses that
order: state never points at an artifact that was deleted before commit.

## Filesystem artifact boundary

The domain passes an opaque source locator through
`InstalledPackageArtifactStore`. The local adapter interprets it as a path,
opens sources with `O_NOFOLLOW`, copies in bounded chunks, verifies SHA-256,
fsyncs, and atomically installs into a coordinate-owned location. Existing and
rollback artifacts are re-hashed before idempotent reuse or activation.

Package lifecycle state is selection metadata, not runtime activation. Phase
6.7 supplies concrete package definitions and runtime adapters; Phase 7 owns
live admission, placement, memory, transfer, and eviction decisions.
