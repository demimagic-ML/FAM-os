# ADR 0132: Production peer trust uses persistent device roots and mutual TLS

**Status:** Accepted  
**Date:** 2026-07-17  
**Supersedes for production transport:** ADR 0099

## Context

Phase 12 proved signed ephemeral X25519 keys and AES-GCM envelopes only through
logical loopback roles. Its identity and transport classes had no production
callers, no persistent private identity, no installed listener, and no restart
trust state. A production peer fabric also needs a manual ceremony that binds
the human-approved device identity to the certificate accepted by the network
stack.

## Decision

Each installed owner profile creates one persistent Ed25519 device root under
the private FAM_OS state directory. The root issues a separate two-year TLS leaf
with both client and server usages. The root identity, TLS key, certificate, and
chain are mode `0600` beneath a mode `0700` directory, are serialized under a
process lock, and fail closed on partial, linked, misowned, mismatched, expired,
or tampered material. Identity is never silently replaced.

Pairing exchanges two signed, ten-minute offers containing the persistent
identity certificate, endpoint, and fresh nonce. Both devices calculate the
same 12-digit comparison code from the complete ordered offers. The code is an
owner comparison aid, not the cryptographic trust anchor. Each owner must pass
literal confirmation after comparing it; FAM_OS then creates a local signature
over the peer approval and stores that approval as owner-encrypted, revisioned
enrollment state.

The installed peer listener is disabled by default. It starts only when an
owner-private versioned configuration enables it and at least one active
enrollment exists. Transport is TLS 1.3 only, requires certificates in both
directions, trusts only enrolled device roots, and post-validates the leaf SAN,
issuer, signature, validity, and expected device identity. Frames are bounded
to one MiB. The Phase 21.1 endpoint accepts only a typed health request; it has
no prompt, file, memory, inference, scheduling, or action authority.

The Phase 12 custom encrypted-channel implementation remains historical
acceptance evidence. It is not the production socket transport.

## Consequences

- Discovery can advertise only already enrolled devices and cannot create
  trust.
- Restart preserves the same root and leaf identities and rebuilds trust from
  encrypted enrollment records.
- A valid but unpaired device certificate fails the TLS handshake.
- Revocation removes an enrollment from the active trust set; live reload and
  the remaining capability, performance, and privacy records belong to Phase
  21.2.
- Remote task payloads remain prohibited until Phase 21.3 defines and enforces
  minimum approved context.
- Localhost evidence can qualify the installed component boundary but cannot
  satisfy the Phase 21.7 physical two-machine gate.
