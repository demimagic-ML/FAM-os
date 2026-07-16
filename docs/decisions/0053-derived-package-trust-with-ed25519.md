# ADR 0053: Derive package trust from policy, digest, license, and Ed25519 evidence

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Package metadata already declares artifact digest, license, trust level, and an
optional signing-key ID. Those values are untrusted claims. Phase 6.3 needs an
admission decision that cannot be obtained by editing a manifest, reusing a
signature for another message type, swapping artifact bytes, claiming a
built-in identity, or choosing an unapproved license.

## Decision

Define strict `fam.registry.trust/v1alpha1` policy, detached-signature, and
validation-report roots. Derive effective trust in `ExpertPackageValidator`
from a trusted policy plus independently observed artifact evidence.

Admit SHA-256 artifacts only. Evaluate bounded SPDX expression grammar against
an exact trusted allowlist. Verify signed packages with active
publisher-bound Ed25519 public keys over a domain-separated canonical current
expert-manifest document. Treat key revocation and every verifier error as a
closed failure.

Grant built-in trust only through an exact configured package/version/publisher
/digest anchor. Deny local-unverified packages unless policy explicitly allows
them. Keep cryptographic verification and filesystem hashing behind adapters;
Registry owns trust policy and decisions. Expose no runtime private-key or
signing interface.

## Consequences

- Manifest `trust_level` is never sufficient admission evidence.
- Artifact, manifest, license, publisher, key, and signature changes are bound
  into one decision.
- Effective trust is explicit and absent on rejection.
- Revoked keys immediately prevent new validation under a refreshed trusted
  policy; installed-package revocation response remains Phase 6.5/14 work.
- The license parser validates structure while the trusted policy owns the
  curated identifier/legal decision.
- Three new strict schema roots increase the catalog to 46 documents.
- `cryptography` is an explicit runtime dependency for the Ed25519 mechanism.

## Alternatives considered

1. Trust the manifest enum: rejected because any package author can edit it.
2. Sign artifact bytes without the manifest: rejected because capabilities,
   license, publisher, resources, and verifier requirements could be changed.
3. Sign undomained JSON: rejected because cross-protocol signature reuse would
   remain ambiguous.
4. Invoke the OpenSSL CLI from policy code: rejected because process mechanics
   and provider output would leak into the Registry boundary.
5. Accept every syntactically valid license: rejected because local legal and
   distribution policy must be explicit.
6. Treat built-ins as unsigned packages by name: rejected because package names
   are untrusted and anchors must bind exact bytes.

## Evidence

- `src/fam_os/registry/trust_contracts.py`
- `src/fam_os/registry/license_policy.py`
- `src/fam_os/registry/signing_payload.py`
- `src/fam_os/registry/validation.py`
- `src/fam_os/adapters/crypto/ed25519.py`
- `src/fam_os/adapters/filesystem/artifact_digest.py`
- `tests/unit/test_package_trust_validation.py`
- `schemas/v1alpha1/fam.registry.*.schema.json`
