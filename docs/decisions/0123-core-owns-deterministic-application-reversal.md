# ADR 0123: Core owns deterministic application reversal

**Status:** Accepted  
**Date:** 2026-07-17

## Context

A reversible connector action returns an opaque reversal token. Asking a model
to reproduce that token would make undo probabilistic, disclose mutation
authority in prompts, and permit the model to change the resource or capability.
Treating undo as a direct connector call would bypass the normal Application
Fabric plan, preview, confirmation, audit, postcondition, and final-result
boundaries.

The Console also needs restart-safe reversal status and must prevent concurrent
or repeated consumption. A human-visible preview must remain structured JSON
without exposing the opaque token.

## Decision

Core owns `ApplicationReversalService`. It accepts only a completed verified
application action that declares a live reversal capability and token. It binds
the original application instance and resource, re-observes the current VS Code
document revision, and seeds the encrypted token as private deterministic
candidate evidence. The model is not invoked for reversal.

The reversal is still a new durable application task with a permission grant,
immutable plan, deterministic proposal, explicit approval, connector action,
independent postcondition, and normal final-result release. The public candidate
is replaced with a fixed safe statement after verification.

Application execution records persist both source and active reversal task
identities. A compare-and-swap claim rejects concurrent undo. Cancelled or
failed attempts may be retried; a verified linked reversal makes the source
permanently report `reversal_already_completed`.

Connector previews omit reversal tokens. Core thaws validated immutable payloads
into a real JSON tree solely for human preview serialization; it does not weaken
the immutable connector boundary.

Phase 19 qualification must run from a newly built Ed25519-signed seven-component
bundle, install its VSIX in an isolated real VS Code profile, and drive summary,
test, edit, and undo through the installed Console API. Source-only or fake-only
tests cannot satisfy the phase exit gate.

## Consequences

- Undo is deterministic and cannot be invented or redirected by a model.
- Opaque reversal authority remains private while the user sees the exact
  resource, edit, and restore digest being approved.
- A reversal can fail closed when the document revision or connector instance
  changes; Core never silently performs a best-effort undo.
- Durable linking adds optional fields to the existing v1alpha1 application
  execution contract and remains backward-compatible with older records.
- The installed qualification requires local Ollama, a graphical VS Code host,
  and enough time to build a complete wheelhouse and signed bundle.
