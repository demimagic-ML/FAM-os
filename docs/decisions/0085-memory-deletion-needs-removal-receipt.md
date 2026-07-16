# ADR 0085: Memory deletion requires a payload-removal receipt

- Status: accepted
- Date: 2026-07-16

## Decision

Memory uses the existing record, scope, provenance, retention, and expiry manifest. Deletion adds a separate owner/actor-bound request and a receipt that can exist only when payload removal is confirmed. The receipt retains digests and identifiers, never the deleted content.

Expiry evaluation is deterministic from explicit timestamps. Expiry and deletion are related but distinct: expiry makes a record ineligible; deletion removes its payload and emits proof.

## Consequences

- Expired data cannot be mistaken for deleted data.
- Users can later inspect deletion history without resurrecting content.
- Storage implementations must verify removal before creating a receipt.
- Authorization remains outside data contracts and cannot be inferred from possession of a request document.
