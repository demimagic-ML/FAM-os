# Cryptographic adapters ownership

Owns replaceable cryptographic mechanisms only. Trust roots, publisher policy,
license admission, package lifecycle, and effective-trust decisions remain in
the Registry component.

Phase 6.3 implements detached Ed25519 verification through `cryptography`.
Private-key generation and signing are deliberately not runtime interfaces.
