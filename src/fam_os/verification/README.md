# Verification ownership

Owns verifier selection, deterministic verdicts, evidence, and release-gating interfaces.

Verifier implementations and sandbox runners are separate small modules. A model claim is never a verification verdict.

Phase 1.8 implements trusted Python candidate extraction, AST policy, deterministic test bundles, verdict conversion, and provider-neutral verifier and sandbox ports. Bubblewrap remains a concrete adapter. Validation, test failure, timeout, and missing isolation are distinct outcomes, and only a passing report may support result release.

`VerifierManifest` adds the `fam.verifier.manifest/v1alpha1` static package declaration. It names acceptance/evidence schemas, determinism, timeout, network policy, and provider-neutral isolation capabilities rather than a concrete sandbox. Live requests and reports remain separate. See `docs/protocols/MANIFEST_CONTRACTS.md` and ADR 0016.
