# ADR 0090: Persistent memory payloads use owner-bound AEAD

- Status: accepted
- Date: 2026-07-16

## Decision

Persistent content and embeddings use AES-256-GCM with a distinct owner key and owner ID as associated data. Routing/scope metadata stays queryable, while payload and vector values are encrypted. Key material is runtime-only and excluded from schemas and artifacts.

## Consequences

- Copying ciphertext into another owner partition fails authentication.
- Database theft does not reveal content or vectors without owner keys.
- Metadata confidentiality is not claimed.
- Production deployment must back owner keys with OS credential storage and restrictive file permissions.
