# Handoff 0069: Verifier trust activation

**Date:** 2026-07-16  
**Plan step:** Phase 8.1  
**Status:** Complete  
**Previous handoff:** `0068-bounded-predictive-prefetch.md`

## Objective

Ensure that only the exact trusted verifier artifact, running through declared
authority and isolation, can participate in an acceptance decision.

## Scope completed

- Added exact verifier package/version/runner/entry-point/digest runtime binding.
- Added verifier-specific digest, license, built-in anchor, Ed25519 publisher,
  revocation, and explicit local-development package validation.
- Added minimum-trust and verifier/runner allowlists.
- Bound activation to declared acceptance, candidate, and evidence schemas.
- Required every manifest isolation capability and policy network denial.
- Added strict runtime-binding, trust-policy, and activation-decision schemas.
- Captured a real implementation digest, successful built-in activation, and
  fail-closed tampered-digest evidence.
- Added unit/contract tests, protocol documentation, and ADR 0068.

## Key files

- `src/fam_os/verification/runtime_binding.py`
- `src/fam_os/verification/package_validation.py`
- `src/fam_os/verification/trust.py`
- `tools/run_verifier_trust_activation.py`
- `artifacts/verification/phase8.1/verifier-trust-activation.json`
- `docs/protocols/VERIFIER_TRUST_ACTIVATION.md`
- `docs/decisions/0068-verifier-activation-is-exact-and-fail-closed.md`

## Validation and evidence

The canonical run hashed `src/fam_os/verification/python/verifier.py` as
`0c0992af3e1e111ba21b2dafcd0162f924fc9272dcaf4ceda37d85e8ab4678b4`.
The exact built-in package and activation policies accepted it. Replacing the
runtime-binding digest returned `runtime.binding_mismatch` and exposed no
verified digest. Generated schema count increased from 76 to 79.

## Explicit limits

This phase proves identity, provenance, authority, and activation admission. It
does not claim hostile-code containment or additional verifier families; Phase
8.2 and later steps own those properties.

## Recommended next entry point

Begin Phase 8.2 by threat-modeling the existing Python subprocess sandbox,
testing its actual kernel boundary, and replacing any advisory-only limits with
fail-closed containment while preserving a documented degraded mode.
