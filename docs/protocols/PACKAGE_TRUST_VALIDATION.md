# Package Trust Validation

## Purpose

Phase 6.3 turns package trust from a manifest claim into derived validation
evidence. A package is admissible only when its observed artifact digest,
license policy, declared trust mode, configured trust roots, and detached
signature requirements all agree.

The strict policy, signature, and report contracts use
`fam.registry.trust/v1alpha1`.

## Inputs and trust boundary

```text
untrusted current ExpertManifest
untrusted detached PackageSignature
observed artifact SHA-256
trusted PackageTrustPolicy
trusted Ed25519 verification mechanism
  -> ExpertPackageValidator
  -> accepted/rejected PackageValidationReport
```

`PackageMetadata.trust_level` remains a declaration. The validator derives
`effective_trust`; it never copies the declaration into an accepted report.
Rejected reports have no effective trust and contain stable reason codes rather
than signature bytes, public keys, file paths, or provider exceptions.

## Artifact integrity

Only SHA-256 package artifact digests are currently admitted. The declared
manifest digest is compared in constant-time with an independently observed
digest before license or signature admission.

`Sha256FileArtifactHasher` provides the first read-only observation adapter. It
uses a configured byte ceiling, bounded chunks, a regular-file check, and
`O_NOFOLLOW` where available. The signed payload contains the declared digest;
changing either artifact bytes or the manifest invalidates admission.

## License policy

`PackageTrustPolicy.allowed_license_expressions` is an exact allowlist. Entries
and package claims must satisfy the bounded SPDX expression grammar for simple
identifiers, `+`, `WITH`, `AND`, `OR`, parentheses, and optionally
`LicenseRef`. Unknown aliases are never normalized.

The parser validates expression structure; the trusted policy author owns the
curated license identifiers and legal decision. FAM does not infer license
compatibility or provide legal advice. `LicenseRef` is disabled unless policy
explicitly enables it and allowlists the exact expression.

The grammar follows the normative SPDX license-expression form documented in
[SPDX Specification Annex D](https://spdx.github.io/spdx-spec/v2.3/SPDX-license-expressions/).

## Signed packages

Signed packages use detached Ed25519 signatures. The signed message is:

```text
"FAM_OS_EXPERT_PACKAGE_SIGNATURE_V1\0" || canonical ExpertManifest document
```

Domain separation prevents a valid signature from being reused as another FAM
message type. Canonical encoding includes the exact schema ID, contract
version, package coordinate, publisher, license expression, artifact digest,
capabilities, resources, runtime contract, and required verifier IDs.

Admission requires:

1. a signature whose key ID equals the manifest claim;
2. a configured active `TrustedPublisherKey` for that key ID;
3. exact publisher and algorithm agreement;
4. successful Ed25519 verification over the canonical domain-separated bytes.

Revoked, unknown, mismatched, malformed, or invalid keys/signatures fail
closed. Verification uses the `cryptography` Ed25519 public-key API documented
by [Cryptography](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).
Runtime code contains no private-key generation or signing interface.

## Built-in and local-unverified packages

`built_in` effective trust requires an exact trusted anchor containing package
ID, version, publisher, and artifact digest. A package cannot self-assert this
level. Built-ins reject signature/key claims so signed and image-anchored trust
cannot be confused.

`local_unverified` effective trust is denied by default. Policy must explicitly
enable it, and the package may carry no signature. This level remains distinct
from signed trust in every report and later installation decision.

## Versioned contracts

- `PackageSignature` carries bounded strict-base64 Ed25519 signature bytes.
- `PackageTrustPolicy` carries exact licenses, publisher public keys and
  revocation states, built-in anchors, and local-package policy.
- `PackageValidationReport` carries safe decision evidence and effective trust.

All three have generated Draft 2020-12 schemas. Private keys and package file
paths never enter these contracts.

## Deferred lifecycle

Validation does not install, enable, activate, or select a package. Phase 6.4
must add hardware/resource compatibility. Phase 6.5 must require accepted trust
and compatibility reports before durable install/update/rollback state changes.
Key distribution, rotation, and external transparency are deployment concerns
that Phase 14 must operationalize.
