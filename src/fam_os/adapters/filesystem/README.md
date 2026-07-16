# Filesystem adapters ownership

Owns bounded local file representations behind domain ports. It contains no
package trust, installation, routing, or lifecycle policy.

`DirectoryExpertManifestSource` reads strict current expert-manifest documents
from one configured directory for Phase 6.2 registry discovery.

`ImmutablePackageArtifactStore` performs no-follow, digest-checked, atomic
artifact ingestion into coordinate-owned paths. `JsonPackageLifecycleStateStore`
provides locked, fsynced, revision-CAS installation state. Trust, compatibility,
enablement, rollback, and removal policy remain in Registry.

The two `DirectoryExpert*MetadataSource` adapters read bounded, no-follow,
strict routing-embedding or benchmark-run documents. They never interpret
quality, disclosure, or routing policy.
