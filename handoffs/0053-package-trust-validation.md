# Handoff 0053: Package trust validation

**Date:** 2026-07-16  
**Plan step:** Phase 6.3  
**Status:** Complete  
**Previous handoff:** `0052-local-expert-registry.md`

## Objective

Turn package digest, license, signature, and trust metadata from self-asserted
manifest fields into a fail-closed effective-trust decision backed by observed
artifact bytes and configured local policy.

## Scope completed

- Strict `fam.registry.trust/v1alpha1` package-signature, trust-policy, and
  validation-report schema roots.
- Independently observed bounded no-follow SHA-256 file artifact hashing.
- Bounded SPDX-shaped license-expression parsing with exact policy allowlists
  and default-disabled `LicenseRef` support.
- Domain-separated canonical signing bytes covering the entire current expert
  manifest, including declared artifact digest.
- Detached Ed25519 verification behind a replaceable Registry port and focused
  `cryptography` adapter.
- Publisher/key/algorithm binding, active/revoked key status, strict base64 and
  Ed25519 length validation, and fail-closed verifier exceptions.
- Exact built-in package/version/publisher/digest anchors preventing trust
  self-assertion.
- Default-denied local-unverified packages with explicit policy opt-in.
- Safe validation reports whose effective trust is absent on every rejection.
- Tampered artifact, manifest, signature, revoked key, unanchored built-in,
  license, local policy, real file hash, and symlink regression tests.

## Explicitly not completed

- Resource/hardware compatibility; Phase 6.4 owns it.
- Durable installation, update, disable, rollback, removal, and revocation
  response for already-installed packages; Phase 6.5 owns lifecycle state.
- Publisher key acquisition, transparency, online revocation distribution, or
  key rotation operations; deployment hardening remains Phase 14 work.
- Legal compatibility inference. The trusted policy author owns curated license
  identifiers and allow decisions.
- Any runtime private-key generation or signing API.

## Architecture and decisions

ADR 0053 separates untrusted declarations from effective trust. The Registry
component owns policy and decision semantics; cryptography and filesystem byte
observation remain adapters. Signatures cover canonical schema documents under
a FAM-specific domain, preventing manifest-field substitution and ambiguous
cross-protocol reuse. Built-in trust is anchored separately from publisher
signature trust, and local-unverified remains visibly weaker.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/registry/trust_contracts.py` | Versioned keys, anchors, policy, signatures, and reports. |
| `src/fam_os/registry/license_policy.py` | Bounded SPDX-shaped grammar and exact allow policy. |
| `src/fam_os/registry/signing_payload.py` | Canonical domain-separated signature payload. |
| `src/fam_os/registry/validation.py` | Digest/license/trust validation policy. |
| `src/fam_os/registry/ports.py` | Replaceable signature-verification port. |
| `src/fam_os/adapters/crypto/ed25519.py` | Ed25519 public-key verification mechanism. |
| `src/fam_os/adapters/filesystem/artifact_digest.py` | Bounded no-follow SHA-256 file observation. |
| `schemas/v1alpha1/fam.registry.*.schema.json` | Three generated trust-boundary schemas. |
| `tests/unit/test_package_trust_validation.py` | Positive and adversarial trust tests. |
| `docs/protocols/PACKAGE_TRUST_VALIDATION.md` | Trust validation protocol. |
| `docs/decisions/0053-derived-package-trust-with-ed25519.md` | Durable security decision. |

## Public interfaces

- `PackageSignature`, `SignatureAlgorithm`
- `TrustedPublisherKey`, `PublisherKeyStatus`
- `BuiltInPackageAnchor`, `PackageTrustPolicy`
- `PackageValidationRequest`, `PackageValidationReport`
- `PackageSignatureVerifier`, `ExpertPackageValidator`
- `PACKAGE_SIGNATURE_DOMAIN`, `expert_package_signing_payload`
- `validate_spdx_expression`, `require_allowed_license`
- `Ed25519PackageSignatureVerifier`
- `Sha256FileArtifactHasher`

## Validation

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
python3 <AST module/function size gate>
```

Result: all 46 generated schemas and compileall passed. Both Python
environments passed 571 tests with three expected environment-dependent skips
each. The size gate found no implementation file above 300 lines and no Python
function above 50 lines across 348 inspected implementation files.
Larry indexed 813 files / 2,496 symbols with 11,341 nodes / 43,582 edges;
freshness and verification were clean. The code knowledge graph was refreshed
to the same 11,341-node / 43,582-edge source view.

## Evidence and artifacts

- `schemas/v1alpha1/fam.registry.package-signature.schema.json`
- `schemas/v1alpha1/fam.registry.trust-policy.schema.json`
- `schemas/v1alpha1/fam.registry.validation-report.schema.json`
- `tests/unit/test_package_trust_validation.py`
- `docs/protocols/PACKAGE_TRUST_VALIDATION.md`
- `docs/decisions/0053-derived-package-trust-with-ed25519.md`

## Known limitations and risks

- Policy validates expression grammar but does not bundle the evolving SPDX
  license list; trusted configuration must use reviewed identifiers.
- The default file hasher supports one regular artifact file. Phase 6.5 must
  define a deterministic package/archive layout before directory packages.
- Key policy is injected trusted configuration; secure distribution, rotation,
  and external audit are not yet operationalized.
- Validation reports are admission evidence, not installation state or a
  durable lifecycle audit.

## Operational notes

`cryptography>=41,<47` is now an explicit dependency. The current system and MCP
test environments already provide a compatible version. No private keys,
signatures, packages, services, models, ports, or machine configuration were
created or changed by validation.

## Recommended next entry point

Begin Phase 6.4. Read `ExpertResourceRequirements`, host inventory/effective
budget contracts, validation profiles, the local expert registry, and the
accepted package validation report. Define a pure compatibility report that
distinguishes hard minimums, optional acceleration, architecture support,
storage availability, and profile-specific schedulable capacity before Phase
6.5 consumes both trust and compatibility evidence.
