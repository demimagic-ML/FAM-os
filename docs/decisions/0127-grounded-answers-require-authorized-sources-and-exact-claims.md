# ADR 0127: Grounded answers require authorized sources and exact claims

**Status:** Accepted  
**Date:** 2026-07-17

## Context

The installed product could retain approved documents and could verify retrieval
citations, but ordinary identity and project questions still followed the
unverified conversation path. That allowed a model to invent what FAM_OS was or
describe a project without consuming the user's approved index. A verified
citation alone was also insufficient if uncited prose could remain in the
released answer.

## Decision

Core deterministically classifies FAM_OS identity, project, repository, citation,
and retrieval requests as grounded. Production prepares those requests before
planning through a typed grounding port. FAM Shell and Console use the trusted
application identity `fam.shell`; authenticated MCP ingress uses `fam.mcp`.
Owner, purpose, application, session, workspace, and expiry checks happen before
source bytes enter a model prompt. A workspace-restricted grant is unavailable
when no trusted workspace identity is present; it is never broadened implicitly.

FAM_OS product identity comes from an immutable package resource in the signed
release. Project sources come only from active encrypted document grants. The
retriever loads the grant's exact embedding model, applies similarity, source
count, and aggregate character limits, derives content and provenance digests,
and treats all retrieved text as untrusted evidence rather than instructions.
If no authorized source exists, request creation fails closed with one safe
instruction to approve a relevant document or folder.

The model must return strict JSON whose answer is exactly the ordered claim texts
joined by newline. Every claim names one declared source and copies an exact
contiguous quote. A single shared parser is used by both the signed retrieval
verifier and terminal presentation. The result is released only after the
signed verifier checks source digests, spans, quote digests, and every claim.
Terminal presentation then replaces raw JSON with the natural answer and typed
exact citations containing source locator, provenance, character span, quote,
and digests. Shell, Console, and MCP preserve the same result citations.

## Consequences

- FAM_OS identity answers are correct and cited without requiring user indexing.
- Project answers require explicit active source authority and survive restart
  only while that authority remains active.
- Cross-application, expired, and unavailable workspace sources never enter the
  prompt.
- A model cannot append an uncited sentence to a verified answer.
- Generated JSON remains internal; users receive natural text plus exact source
  evidence.
- Source verifier manifests and runtime bindings must be re-digested whenever
  executable verifier Python changes.
- Phase 20.4 remains responsible for inspect, correct, export, expire, and delete
  management controls and durable receipts.
