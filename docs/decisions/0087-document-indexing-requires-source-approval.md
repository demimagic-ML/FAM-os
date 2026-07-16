# ADR 0087: Document indexing requires digest-bound source approval

- Status: accepted
- Date: 2026-07-16

## Decision

Durable document indexing has one entrypoint and it requires a `DocumentIndexApproval`. Approval binds exact source bytes, scope, actor/time, and embedding artifact. Chunk concatenation must reproduce the approved source exactly. Retrieval filters scope before scoring.

## Consequences

- A crawler or connector cannot silently add arbitrary user files.
- Changed source bytes require new approval or an explicit update workflow.
- Embeddings remain attributable to an exact model artifact.
- Until Phase 10.6 encryption lands, this store is evidence-grade and must not hold sensitive production data.
