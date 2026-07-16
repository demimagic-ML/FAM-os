# ADR 0068: Verifier activation is exact and fail-closed

**Status:** Accepted  
**Date:** 2026-07-16

## Context

A verifier can authorize release of model output. A static capability manifest
alone does not prove which bytes will run, who published them, what acceptance
policy they may decide, or whether required isolation exists.

## Decision

FAM retains the compatible verifier manifest and adds independent package
validation, exact runtime binding, and activation policy contracts. Activation
requires the same package coordinate and SHA-256 digest across manifest,
observed validation evidence, and runtime binding. Verifier, runner, acceptance,
candidate schema, evidence schema, trust floor, and isolation are all allowlisted
or declared. Every mismatch fails closed with a stable reason.

Verifier signatures use a verifier-specific domain-separated canonical payload;
they cannot be replayed as expert-package signatures.

## Consequences

- A package cannot gain release authority merely by registering a manifest.
- Local unverified packages remain usable only under explicit development policy.
- Trust and runtime identity are auditable independently from sandbox execution.
- Sandbox containment and family-specific correctness remain separate gates.
