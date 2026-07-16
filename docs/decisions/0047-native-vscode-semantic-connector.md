# ADR 0047: Use native transport for the first VS Code semantic connector

**Status:** Accepted  
**Date:** 2026-07-16  
**Plan step:** Phase 5.9

## Context

The first editor connector must provide useful high-fidelity observations and a
real reversible action without allowing a model or extension to bypass Core.
VS Code provides semantic document, selection, diagnostic, and `WorkspaceEdit`
APIs, while Application Fabric already defines permissioned observation,
proposal, confirmation, action, postcondition, and reversal contracts.

MCP can expose editor tools, but it is neither the internal capability model nor
the permission boundary. Making it mandatory here would add a second action
lifecycle around the exact semantics already carried by the authenticated native
transport.

## Decision

Implement a small TypeScript VS Code extension and provider-neutral reference
connector SDK over `fam.applications.local/v1alpha1`.

- Keep VS Code SDK imports inside editor adapter/composition modules.
- Register three bounded observation capabilities and two always-confirmed,
  reversible workspace-edit capabilities.
- Separate metadata, selected text, and diagnostics authorities.
- Bind edits to workspace scope, exact URI, document version, and SHA-256.
- Reject large documents/edits, invalid UTF-16 positions, overlaps, duplicate
  insert positions, stale revisions, and unrecognized fields before mutation.
- Revalidate immediately before `workspace.applyEdit` and emit verified status
  only after deterministic buffer hash/version postconditions pass.
- Store bounded opaque reversal records only in extension memory; revalidate
  again before undo and clear all records on disconnect.
- Require a correlated Core ACK before reporting connected.
- Keep the extension off by default and reconnect on workspace-scope changes.
- Do not embed an MCP server in the initial extension. Future read-only MCP
  surfaces may be mapped through the existing MCP adapter, but action authority
  must retain the same Core lifecycle.

## Consequences

VS Code becomes the first real level-1 semantic application connector without
introducing provider types into Core. The same TypeScript SDK can guide later
native connectors. The edit is reversible only while the bounded extension
process remains connected and the buffer has not changed; that conservative
scope is visible and testable.

Editor evidence confirms in-memory buffer state. Saved-file hashes, compilation,
and tests remain independent deterministic postconditions composed by Core.
This avoids claiming that `WorkspaceEdit` success proves the full user task.

The extension is source/lockfile reproducible and can be packaged locally, but
package signing, registry trust, sandbox lifecycle, update, and installation are
deferred to the planned package system and deployment phases.

## Alternatives rejected

- A generic `executeCommand` capability is too broad and effect classification
  would be unstable.
- Screen/input automation loses editor semantics and is only the Phase 5.10
  fallback.
- Filesystem-only writes cannot see dirty buffers, selections, diagnostics, or
  document versions and could conflict with editor state.
- VS Code's global Undo command can reverse unrelated user work after an
  intervening action; exact token-bound full-document reversal is safer.
- An MCP-only connector would either duplicate or weaken the required native
  permission, approval, correlation, postcondition, and reversal lifecycle.
