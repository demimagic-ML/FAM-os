# ADR 0089: Memory correction is an atomic reindex

- Status: accepted
- Date: 2026-07-16

## Decision

Correcting persistent document memory replaces source approval, digest, chunks, and embeddings in one transaction. Export re-hashes reconstructed content. Deletion cascades payload rows before producing a receipt.

## Consequences

- Queries cannot observe mixed old/new chunks.
- Correction requires fresh source digest evidence.
- Export detects database/content tampering.
- Deletion is inspectable without retaining payload.
