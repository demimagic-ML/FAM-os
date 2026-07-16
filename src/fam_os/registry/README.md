# Registry ownership

Owns expert, verifier, connector, and schema package identity, signatures, compatibility, installation state, and rollback metadata.

Registry code does not execute packages. Execution remains inside the relevant isolated component.

`PackageMetadata` is the shared identity, version, publisher, license, digest, and declared-trust fragment composed by expert, verifier, and connector manifests. Shape validation does not verify a signature or confer trust; cryptographic validation and lifecycle remain Phase 6 work. See `docs/protocols/MANIFEST_CONTRACTS.md` and ADR 0016.

Phase 6.3 adds strict trust policy, detached signature, and validation-report
contracts. `ExpertPackageValidator` derives effective built-in, signed, or
local-unverified trust from observed SHA-256, exact license policy, configured
anchors/keys, and the replaceable signature-verifier port. See
`docs/protocols/PACKAGE_TRUST_VALIDATION.md` and ADR 0053.

Phase 6.5 adds the durable side-by-side expert package lifecycle. Installation
state records exact trust, compatibility, artifact and manifest digest
evidence; updates retain rollback versions; and removals use recoverable
pending-deletion tombstones. See
`docs/protocols/EXPERT_PACKAGE_LIFECYCLE.md` and ADR 0055.

Reference model packages may point at externally owned runtime artifacts. The
runtime catalog must observe an exact digest and size; package removal never
implies deletion of the user's provider artifact. See ADR 0057.
