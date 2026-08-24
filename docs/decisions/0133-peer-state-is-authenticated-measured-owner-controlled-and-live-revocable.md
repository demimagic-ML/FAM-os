# ADR 0133: Peer state is authenticated, measured, owner-controlled, and live-revocable

**Status:** Accepted  
**Date:** 2026-07-17  
**Extends:** ADR 0132

## Context

Phase 21.1 established persistent roots, manual pairing, encrypted enrollment,
and mutual TLS, but its listener accepted health only. A stored enrollment alone
does not establish what a peer can run, how it performs, what context the owner
allows, or whether a revocation has reached the live listener. Treating
self-reported latency as measurement or network discovery as enrollment would
weaken the trust boundary.

## Decision

An authenticated peer may answer `describe` with exact expert declarations
signed by its persistent Ed25519 device root. Each declaration binds the device,
expert, runtime model, canonical capability IDs, context-byte ceiling, installed
manifest digest, revision, and validity interval. The receiving device verifies
the signature against its enrolled identity before storing the declaration.

Performance is never copied from the peer declaration. The receiving device
measures mutual-TLS request round-trip and response size locally and binds the
observation to the authenticated server leaf digest. Capabilities, performance,
per-peer privacy policies, and management receipts are encrypted at rest.
Performance retention is bounded to the latest 100 observations per enrollment.

The trusted directory is a projection of active encrypted enrollments. It has no
enrollment operation and cannot display or advertise an unpaired device. Missing
privacy policy means deny all. Policy changes bind exactly one active peer and
require owner identity, expected revision, literal confirmation, and a durable
replay-safe receipt.

Revocation is committed atomically with its receipt. The service closes the
listener before rebuilding its TLS trust set. Every accepted control message also
rechecks active enrollment after TLS authentication, so a stale context cannot
exercise authority between database commit and listener replacement. Revocation
persists across restart and removes the peer from discovery immediately.

Shell and the authenticated loopback Console expose list, probe, privacy,
receipt, and revoke operations. Console mutations remain Origin-, CSRF-, owner-,
revision-, and confirmation-bound.

## Consequences

- Signed capability claims are distinguishable from locally measured performance.
- Discovery never expands trust.
- A revoked peer cannot use the control endpoint and is absent after restart.
- Capability presence does not authorize remote context or execution. Phase 21.3
  must apply the stored privacy policy and send only minimum approved context.
- The signed two-install exit is same-host evidence; it does not satisfy the
  Phase 21.7 physical-machine gate.
