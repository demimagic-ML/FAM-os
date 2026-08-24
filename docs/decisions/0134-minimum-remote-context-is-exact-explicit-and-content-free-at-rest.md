# ADR 0134: Minimum remote context is exact, explicit, and content-free at rest

**Status:** Accepted  
**Date:** 2026-07-17  
**Extends:** ADR 0133

## Context

Pairing and signed capability discovery do not authorize disclosure. A remote
task can accidentally expose an entire prompt, workspace, retrieved document,
or memory record if context is represented as an unbounded dictionary or if a
network adapter decides policy after sending. Metadata-only audit records are
also insufficient unless they bind the exact bytes that crossed the boundary.

## Decision

FAM_OS uses `fam.fabric.minimum-context/v1alpha1` as a pre-execution disclosure
contract. Its canonical payload contains only an explicit task descriptor and
zero or more typed raw fragments. Raw fragments are limited to prompt,
file-excerpt, memory, and retrieval kinds; each binds source digest, content
digest, and exact UTF-8 content. The complete canonical payload has a 256-KiB
ceiling, exact byte count and digest, two-minute validity, sender/receiver and
request identities, and an Ed25519 device-root signature.

The outbound service evaluates the exact active enrollment, encrypted privacy
revision, peer identity, purpose, workspace, sensitivity, byte ceiling,
raw-content permission, signed capability declaration, expert, required
capabilities, and capability byte ceiling before creating a network client.
Missing policy means zero disclosure. Any raw fragment additionally requires
literal confirmation at the request-contract boundary.

Mutual TLS remains mandatory. The receiver verifies the sender signature,
target device, validity, exact bytes, and current locally installed expert
capability before signing an acceptance receipt. The receipt binds request,
context, sender, responder, byte count, content digest, fragment count, status,
and acceptance time. It does not contain raw content.

Both installations retain encrypted content-free evidence only. Evidence binds
the local send-request digest, remote receipt, exact content digest and byte
count, fragment digests, selected policy revision, capability declaration, and
reason codes. A received raw fragment exists only in the bounded request object
during verification and is discarded after the receipt is committed.

Shell exposes descriptor-only transfer and evidence inspection. Console exposes
an exact-field authenticated endpoint for qualification and owner tooling.
Neither surface performs remote inference. Phase 21.4 must integrate disclosure
with the normal Core lifecycle rather than introduce a second task coordinator.

## Consequences

- Policy or capability denial happens before socket creation.
- A signed receipt proves what digest and byte count the peer accepted, not that
  an expert ran or produced an acceptable answer.
- Allowed raw content is not durable on either machine; only its digest remains.
- Lost-response reconciliation and exactly-once retry remain Phase 21.6 work.
- Same-host installed qualification is strong transport/product evidence but not
  the Phase 21.7 two-physical-machine gate.
