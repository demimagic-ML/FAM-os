# ADR 0119: Installed requests use one durable Core lifecycle

**Status:** Accepted  
**Date:** 2026-07-17

## Context

The installed Shell previously bypassed the implemented Core fabrics and called
one fixed Ollama model through `LocalInferenceShellGateway`. That made the
product behave like a chatbot and prevented restart recovery, policy routing,
resource selection, acceptance verification, and durable final evidence from
being authoritative.

## Decision

The production service uses `ProductionTaskGateway`. Every natural request is
classified by Core policy, receives explicit internal capability authority, is
admitted once, routed without changing that authority, compiled into an
immutable plan, and stored in encrypted repositories before inference.

Model selection uses a release-configured catalog bound to the SHA-256 digest
and size of locally present Ollama manifests. Selection uses current available
host RAM and NVIDIA VRAM. Managed Ollama imports a selected model only after
validating all source blob digests.

Unverified generation can release only as `completed`. Verification-required
generation releases only when a declared deterministic verifier records passing
acceptance evidence. A failed exact-output candidate gets one feedback-bound
repair and one stronger-model escalation under a durable shared budget. Missing
verifiers withhold content rather than treating model confidence as proof.

## Consequences

- Stopping the service after admission no longer loses the task or causes a new
  request identity on restart.
- The default model is an economical policy choice, not a hard-coded product
  architecture.
- Application authority, application postconditions, code sandboxes, grounded
  citations, and broader verifier bindings remain explicit follow-on work; the
  gateway does not simulate them.
- `LocalInferenceShellGateway` remains only as a bounded legacy component and is
  not imported by production composition.

