# Verifier trust and activation

Phase 8.1 separates three facts that must all hold before a verifier may decide
whether output is releasable: the package is trusted, the executable runtime is
the package declared by the manifest, and the requested acceptance authority is
inside that manifest.

## Boundary

`VerifierManifest` remains the static provider-neutral declaration. A
`VerifierPackageValidator` independently observes the SHA-256 artifact digest,
checks the license, and derives built-in, signed, or explicitly allowed local
trust from configured anchors or keys. A validation report is evidence, not an
activation by itself.

`VerifierRuntimeBinding` names the exact package version, verifier, runner
contract, runtime adapter, entry point, and expected artifact digest.
`VerifierTrustEvaluator` then requires all of the following:

- an accepted package report for the exact package and observed digest;
- a trust level at or above policy minimum;
- exact manifest-to-runtime identity and digest binding;
- allowlisted verifier and runner authority;
- declared acceptance, candidate, and evidence schemas;
- every required isolation capability; and
- network denial whenever the activation policy requires it.

Any mismatch returns a stable rejection reason and withholds the verified digest.
There is no permissive fallback.

## Trust meaning

`built_in` requires an exact configured package/version/publisher/digest anchor.
`signed` requires a valid domain-separated Ed25519 signature from an active,
publisher-matching key. `local_unverified` is below both and is denied unless a
package policy explicitly enables it; an activation policy can still demand a
higher minimum.

The canonical Phase 8.1 run hashes the real Python verifier implementation,
validates it against an exact built-in anchor, activates the exact runtime, and
proves a changed runtime digest is rejected. Evidence is in
`artifacts/verification/phase8.1/verifier-trust-activation.json`.

## Security limits

Trust establishes publisher/artifact identity and declared authority. It does
not establish that verifier logic is correct or that a process sandbox contains
hostile code. Those properties require verifier-family tests and Phase 8.2
sandbox hardening. Callers must obtain validation reports from the trusted
registry boundary, not accept reports supplied by an untrusted connector.
